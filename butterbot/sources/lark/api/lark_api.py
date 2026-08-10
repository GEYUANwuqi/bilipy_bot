"""飞书官方 WebSocket 事件传输与常用 IM OpenAPI 的异步封装。"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from dataclasses import dataclass
from logging import getLogger
from typing import IO, Any, Literal, cast
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import lark_oapi as lark
import websockets
from lark_oapi.api.im.v1 import (
    CreateFileRequest,
    CreateFileRequestBody,
    CreateImageRequest,
    CreateImageRequestBody,
    CreateMessageReactionRequest,
    CreateMessageReactionRequestBody,
    CreateMessageRequest,
    CreateMessageRequestBody,
    DeleteMessageReactionRequest,
    DeleteMessageRequest,
    Emoji,
    GetMessageRequest,
    PatchMessageRequest,
    PatchMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)
from lark_oapi.ws.client import Client as SdkWebSocketClient
from lark_oapi.ws.const import DEVICE_ID, SERVICE_ID

from butterbot.core.api import BaseApi
from butterbot.core.context import ApiRegistry
from butterbot.core.exceptions import ApiError
from butterbot.utils.websocket import ConnectionHealth, ConnectionHealthState

_log = getLogger("LarkApi")

LarkEventHandler = Callable[[dict[str, Any]], Awaitable[None]]
LarkHealthHandler = Callable[[ConnectionHealth], None]

_BUILTIN_EVENT_REGISTRATIONS = (
    "register_p2_im_message_receive_v1",
    "register_p2_im_message_message_read_v1",
    "register_p2_im_message_recalled_v1",
    "register_p2_im_message_reaction_created_v1",
    "register_p2_im_message_reaction_deleted_v1",
    "register_p2_im_chat_updated_v1",
    "register_p2_im_chat_disbanded_v1",
    "register_p2_im_chat_access_event_bot_p2p_chat_entered_v1",
    "register_p2_im_chat_member_user_added_v1",
    "register_p2_im_chat_member_user_deleted_v1",
    "register_p2_im_chat_member_user_withdrawn_v1",
    "register_p2_im_chat_member_bot_added_v1",
    "register_p2_im_chat_member_bot_deleted_v1",
    "register_p2_application_bot_menu_v6",
)

_BUILTIN_EVENT_TYPES = {
    "im.message.receive_v1",
    "im.message.message_read_v1",
    "im.message.recalled_v1",
    "im.message.reaction.created_v1",
    "im.message.reaction.deleted_v1",
    "im.chat.updated_v1",
    "im.chat.disbanded_v1",
    "im.chat.access_event.bot_p2p_chat_entered_v1",
    "im.chat.member.user.added_v1",
    "im.chat.member.user.deleted_v1",
    "im.chat.member.user.withdrawn_v1",
    "im.chat.member.bot.added_v1",
    "im.chat.member.bot.deleted_v1",
    "application.bot.menu_v6",
}


@dataclass
class LarkConfig:
    """飞书应用、WebSocket 事件源和 OpenAPI 配置。"""

    app_id: str
    app_secret: str
    verification_token: str = ""
    encrypt_key: str = ""
    domain: str = "https://open.feishu.cn"
    ready_timeout: float = 30.0
    request_timeout: float = 30.0
    custom_event_types: tuple[str, ...] = ()
    deduplicate_events: bool = True
    dedup_ttl: float = 3600.0
    dedup_max_entries: int = 4096

    def __post_init__(self) -> None:
        if not self.app_id or not self.app_id.strip():
            raise ValueError("app_id 不能为空")
        if not self.app_secret or not self.app_secret.strip():
            raise ValueError("app_secret 不能为空")
        if self.ready_timeout <= 0:
            raise ValueError("ready_timeout 必须大于 0")
        if self.request_timeout <= 0:
            raise ValueError("request_timeout 必须大于 0")
        if self.dedup_ttl <= 0:
            raise ValueError("dedup_ttl 必须大于 0")
        if self.dedup_max_entries <= 0:
            raise ValueError("dedup_max_entries 必须大于 0")
        self.custom_event_types = tuple(self.custom_event_types)
        if any(not item or not item.strip() for item in self.custom_event_types):
            raise ValueError("custom_event_types 不能包含空事件名")
        if len(set(self.custom_event_types)) != len(self.custom_event_types):
            raise ValueError("custom_event_types 不能包含重复事件名")
        duplicate_builtin = _BUILTIN_EVENT_TYPES.intersection(self.custom_event_types)
        if duplicate_builtin:
            raise ValueError(
                "custom_event_types 不应重复内置事件: %s"
                % ", ".join(sorted(duplicate_builtin))
            )


class LarkApiError(ApiError):
    """飞书 OpenAPI 返回非零错误码。"""

    def __init__(
        self,
        code: int,
        message: str,
        *,
        log_id: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.log_id = log_id
        detail = "飞书 OpenAPI 调用失败: code=%s, msg=%s" % (code, message)
        if log_id:
            detail += ", log_id=%s" % log_id
        super().__init__(detail)


class _ManagedSdkWebSocketClient(SdkWebSocketClient):
    """为官方 SDK 的协议实现补充 asyncio 生命周期所有权。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._managed_running = False
        self._managed_tasks: set[asyncio.Task[Any]] = set()
        self._transport_error_handler: Callable[[BaseException], None] | None = None

    @property
    def ready(self) -> bool:
        """返回官方 SDK 底层连接是否已完成握手。"""
        return self._managed_running and self._conn is not None

    def set_transport_error_handler(
        self,
        handler: Callable[[BaseException], None],
    ) -> None:
        """设置无法由协议层恢复的后台任务错误观察者。"""
        self._transport_error_handler = handler

    def _spawn(self, coroutine: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task = asyncio.create_task(coroutine)
        self._managed_tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task: asyncio.Task[Any]) -> None:
        self._managed_tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None and self._managed_running:
            _log.error("飞书 WebSocket 后台任务异常: %s", error)
            if self._transport_error_handler is not None:
                self._transport_error_handler(error)

    async def start_managed(self) -> None:
        """连接并创建受当前 asyncio 生命周期管理的协议任务。"""
        if self.ready:
            return
        self._auto_reconnect = True
        self._managed_running = True
        try:
            await self._connect()
            self._spawn(self._ping_loop())
        except BaseException:
            self._managed_running = False
            raise

    async def stop_managed(self) -> None:
        """断开连接并取消由该传输创建的全部协议任务。"""
        if not self._managed_running and not self._managed_tasks:
            return
        self._managed_running = False
        self._auto_reconnect = False
        await self._disconnect()
        tasks = list(self._managed_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _connect(self) -> None:
        async with self._lock:
            if self._conn is not None:
                return
            conn_url = await asyncio.to_thread(self._get_conn_url)
            query = parse_qs(urlparse(conn_url).query)
            conn_id = query[DEVICE_ID][0]
            service_id = query[SERVICE_ID][0]
            kwargs = (
                {"proxy": None}
                if "proxy" in inspect.signature(websockets.connect).parameters
                else {}
            )
            connect = cast(Any, websockets.connect)
            connection = await connect(conn_url, **kwargs)
            self._conn = cast(Any, connection)
            self._conn_url = conn_url
            self._conn_id = conn_id
            self._service_id = service_id
            self._spawn(self._receive_message_loop())

    async def _receive_message_loop(self) -> None:
        try:
            while self._managed_running:
                if self._conn is None:
                    raise ConnectionError("飞书 WebSocket 已断开")
                message = await self._conn.recv()
                self._spawn(self._handle_message(message))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self._managed_running:
                return
            _log.warning("飞书 WebSocket 接收中断: %s", exc)
            await self._disconnect()
            if self._auto_reconnect and self._managed_running:
                await self._reconnect()
            else:
                raise


class LarkClient:
    """同时持有官方 WebSocket 事件传输和异步 OpenAPI 客户端。"""

    def __init__(self, config: LarkConfig) -> None:
        self.config = config
        self._handler: LarkEventHandler | None = None
        self._health_handler: LarkHealthHandler | None = None
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._consumer_task: asyncio.Task[None] | None = None
        self._running = False

        self.openapi_client = (
            lark.Client.builder()
            .app_id(config.app_id)
            .app_secret(config.app_secret)
            .domain(config.domain)
            .timeout(config.request_timeout)
            .build()
        )
        dispatcher = self._build_dispatcher()
        self.websocket_client = _ManagedSdkWebSocketClient(
            config.app_id,
            config.app_secret,
            event_handler=dispatcher,
            domain=config.domain,
            auto_reconnect=True,
        )
        self.websocket_client.on_reconnecting = self._on_reconnecting
        self.websocket_client.on_reconnected = self._on_reconnected
        self.websocket_client.set_transport_error_handler(self._on_transport_error)

    @property
    def running(self) -> bool:
        """返回事件消费者与 WebSocket 是否均处于运行状态。"""
        return self._running and self.websocket_client.ready

    def set_handler(self, handler: LarkEventHandler) -> None:
        """设置接收标准飞书事件 envelope 的异步处理函数。"""
        if not inspect.iscoroutinefunction(handler):
            raise TypeError("handler must be an async function")
        self._handler = handler

    def set_health_handler(self, handler: LarkHealthHandler | None) -> None:
        """设置 WebSocket 就绪、重连与停止状态观察者。"""
        self._health_handler = handler

    def _build_dispatcher(self) -> Any:
        builder = lark.EventDispatcherHandler.builder(
            self.config.encrypt_key,
            self.config.verification_token,
        )
        for registration in _BUILTIN_EVENT_REGISTRATIONS:
            builder = getattr(builder, registration)(self._on_sdk_event)
        for event_type in self.config.custom_event_types:
            builder = builder.register_p2_customized_event(
                event_type,
                self._on_sdk_event,
            )
        return builder.build()

    def _on_sdk_event(self, data: Any) -> None:
        encoded = lark.JSON.marshal(data)
        if encoded is None:
            raise ValueError("飞书 SDK 事件序列化结果为空")
        payload = json.loads(encoded)
        self._queue.put_nowait(payload)

    async def start(self) -> None:
        """连接 WebSocket 并启动事件消费；返回时连接已经就绪。"""
        if self.running:
            return
        if self._handler is None:
            raise RuntimeError("飞书事件处理函数未设置")
        self._consumer_task = asyncio.create_task(self._consume_events())
        try:
            await asyncio.wait_for(
                self.websocket_client.start_managed(),
                timeout=self.config.ready_timeout,
            )
        except BaseException:
            await self.stop()
            raise
        self._running = True
        self._report_health(ConnectionHealthState.READY)

    async def stop(self) -> None:
        """幂等关闭 WebSocket 与事件消费任务。"""
        self._running = False
        first_error: BaseException | None = None
        try:
            await self.websocket_client.stop_managed()
        except BaseException as exc:
            first_error = exc

        task = self._consumer_task
        if task is not None:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except BaseException as exc:
                first_error = first_error or exc
            self._consumer_task = None
        self._report_health(ConnectionHealthState.STOPPED)
        if first_error is not None:
            raise first_error

    async def _consume_events(self) -> None:
        while True:
            payload = await self._queue.get()
            try:
                assert self._handler is not None
                await self._handler(payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                _log.exception("处理飞书事件失败: %s", payload)
            finally:
                self._queue.task_done()

    def _on_reconnecting(self) -> None:
        self._report_health(
            ConnectionHealthState.DEGRADED,
            ConnectionError("飞书 WebSocket 正在重连"),
        )

    def _on_reconnected(self) -> None:
        self._report_health(ConnectionHealthState.READY)

    def _on_transport_error(self, error: BaseException) -> None:
        self._report_health(ConnectionHealthState.DEGRADED, error)

    def _report_health(
        self,
        state: ConnectionHealthState,
        error: BaseException | None = None,
    ) -> None:
        handler = self._health_handler
        if handler is None:
            return
        now = time.time()
        handler(
            ConnectionHealth(
                state=state,
                last_success_at=now if state is ConnectionHealthState.READY else None,
                last_error_at=now if error is not None else None,
                last_error_type=type(error).__name__ if error is not None else None,
                last_error_message=str(error) if error is not None else None,
            )
        )


def _content_json(content: str | Mapping[str, Any]) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(dict(content), ensure_ascii=False)


def _response_data(response: Any) -> dict[str, Any]:
    if not response.success():
        raise LarkApiError(
            response.code,
            response.msg,
            log_id=response.get_log_id(),
        )
    if response.data is None:
        return {}
    encoded = lark.JSON.marshal(response.data)
    if encoded is None:
        return {}
    value = json.loads(encoded)
    return value if isinstance(value, dict) else {"data": value}


class LarkApi(BaseApi):
    """飞书事件连接与常用 IM OpenAPI。"""

    @classmethod
    def create(cls, ctx: ApiRegistry, config_key: str = "lark") -> LarkApi:
        """从 API 注册表的指定配置键创建飞书 API。"""
        return cls(ctx.require_config(config_key))

    def __init__(self, config: LarkConfig) -> None:
        self.config = config
        self.client = LarkClient(config)
        self._im_v1 = cast(Any, self.client.openapi_client.im).v1

    async def aclose(self) -> None:
        """释放 WebSocket 与内部事件任务，供 ``ApiRegistry`` 调用。"""
        await self.stop()

    def set_handler(self, handler: LarkEventHandler) -> None:
        """设置 WebSocket 事件的异步处理函数。"""
        self.client.set_handler(handler)

    def set_health_handler(self, handler: LarkHealthHandler | None) -> None:
        """设置连接健康状态观察者。"""
        self.client.set_health_handler(handler)

    async def start(self) -> None:
        """启动飞书 WebSocket 事件连接并等待首次就绪。"""
        await self.client.start()

    async def stop(self) -> None:
        """幂等停止飞书 WebSocket 事件连接。"""
        await self.client.stop()

    async def send_message(
        self,
        receive_id: str,
        msg_type: str,
        content: str | Mapping[str, Any],
        *,
        receive_id_type: Literal[
            "open_id", "union_id", "user_id", "email", "chat_id"
        ] = "chat_id",
        uuid: str | None = None,
    ) -> dict[str, Any]:
        """发送任意飞书消息，内容可传 JSON 字符串或映射。"""
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type(msg_type)
            .content(_content_json(content))
            .uuid(uuid or str(uuid4()))
            .build()
        )
        request = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(body)
            .build()
        )
        response = await self._im_v1.message.acreate(request)
        return _response_data(response)

    async def send_text(
        self,
        receive_id: str,
        text: str,
        *,
        receive_id_type: Literal[
            "open_id", "union_id", "user_id", "email", "chat_id"
        ] = "chat_id",
    ) -> dict[str, Any]:
        """向用户或群聊发送文本消息。"""
        return await self.send_message(
            receive_id,
            "text",
            {"text": text},
            receive_id_type=receive_id_type,
        )

    async def send_post(
        self,
        receive_id: str,
        content: str | Mapping[str, Any],
        *,
        receive_id_type: Literal[
            "open_id", "union_id", "user_id", "email", "chat_id"
        ] = "chat_id",
    ) -> dict[str, Any]:
        """发送飞书富文本 ``post`` 消息。"""
        return await self.send_message(
            receive_id,
            "post",
            content,
            receive_id_type=receive_id_type,
        )

    async def send_card(
        self,
        receive_id: str,
        content: str | Mapping[str, Any],
        *,
        receive_id_type: Literal[
            "open_id", "union_id", "user_id", "email", "chat_id"
        ] = "chat_id",
    ) -> dict[str, Any]:
        """发送由 JSON 描述的交互式消息卡片。"""
        return await self.send_message(
            receive_id,
            "interactive",
            content,
            receive_id_type=receive_id_type,
        )

    async def reply_message(
        self,
        message_id: str,
        msg_type: str,
        content: str | Mapping[str, Any],
        *,
        reply_in_thread: bool = False,
        uuid: str | None = None,
    ) -> dict[str, Any]:
        """引用回复指定消息，支持普通会话和话题内回复。"""
        body = (
            ReplyMessageRequestBody.builder()
            .msg_type(msg_type)
            .content(_content_json(content))
            .reply_in_thread(reply_in_thread)
            .uuid(uuid or str(uuid4()))
            .build()
        )
        request = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(body)
            .build()
        )
        response = await self._im_v1.message.areply(request)
        return _response_data(response)

    async def reply_text(
        self,
        message_id: str,
        text: str,
        *,
        reply_in_thread: bool = False,
    ) -> dict[str, Any]:
        """引用回复指定消息一段文本。"""
        return await self.reply_message(
            message_id,
            "text",
            {"text": text},
            reply_in_thread=reply_in_thread,
        )

    async def update_message(
        self,
        message_id: str,
        content: str | Mapping[str, Any],
    ) -> dict[str, Any]:
        """更新机器人发送的消息内容。"""
        body = PatchMessageRequestBody.builder().content(_content_json(content)).build()
        request = (
            PatchMessageRequest.builder()
            .message_id(message_id)
            .request_body(body)
            .build()
        )
        response = await self._im_v1.message.apatch(request)
        return _response_data(response)

    async def delete_message(self, message_id: str) -> dict[str, Any]:
        """撤回机器人发送的指定消息。"""
        request = DeleteMessageRequest.builder().message_id(message_id).build()
        response = await self._im_v1.message.adelete(request)
        return _response_data(response)

    async def get_message(
        self,
        message_id: str,
        *,
        user_id_type: Literal["open_id", "union_id", "user_id"] = "open_id",
    ) -> dict[str, Any]:
        """按消息 ID 获取消息详情。"""
        request = (
            GetMessageRequest.builder()
            .message_id(message_id)
            .user_id_type(user_id_type)
            .build()
        )
        response = await self._im_v1.message.aget(request)
        return _response_data(response)

    async def add_reaction(
        self,
        message_id: str,
        emoji_type: str,
    ) -> dict[str, Any]:
        """给指定消息添加一个表情回复。"""
        reaction = Emoji.builder().emoji_type(emoji_type).build()
        body = (
            CreateMessageReactionRequestBody.builder().reaction_type(reaction).build()
        )
        request = (
            CreateMessageReactionRequest.builder()
            .message_id(message_id)
            .request_body(body)
            .build()
        )
        response = await self._im_v1.message_reaction.acreate(request)
        return _response_data(response)

    async def delete_reaction(
        self,
        message_id: str,
        reaction_id: str,
    ) -> dict[str, Any]:
        """按 reaction ID 删除指定消息的表情回复。"""
        request = (
            DeleteMessageReactionRequest.builder()
            .message_id(message_id)
            .reaction_id(reaction_id)
            .build()
        )
        response = await self._im_v1.message_reaction.adelete(request)
        return _response_data(response)

    async def upload_image(
        self,
        image: IO[Any],
        *,
        image_type: Literal["message", "avatar"] = "message",
    ) -> dict[str, Any]:
        """上传消息或头像图片并返回 ``image_key`` 等结果。"""
        body = (
            CreateImageRequestBody.builder().image_type(image_type).image(image).build()
        )
        request = CreateImageRequest.builder().request_body(body).build()
        response = await self._im_v1.image.acreate(request)
        return _response_data(response)

    async def upload_file(
        self,
        file: IO[Any],
        *,
        file_type: Literal["opus", "mp4", "pdf", "doc", "xls", "ppt", "stream"],
        file_name: str,
        duration: int | None = None,
    ) -> dict[str, Any]:
        """上传消息文件并返回 ``file_key`` 等结果。"""
        builder = (
            CreateFileRequestBody.builder()
            .file_type(file_type)
            .file_name(file_name)
            .file(file)
        )
        if duration is not None:
            builder = builder.duration(duration)
        request = CreateFileRequest.builder().request_body(builder.build()).build()
        response = await self._im_v1.file.acreate(request)
        return _response_data(response)
