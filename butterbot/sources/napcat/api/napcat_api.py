import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from logging import getLogger
from typing import Any
from uuid import uuid4

from butterbot.core.api import BaseApi
from butterbot.core.context import ApiRegistry
from butterbot.utils.websocket import (
    AsyncWebSocketClient,
    ConnectionHealth,
    ListenerClosedError,
    ListenerEvictedError,
    ListenerId,
    MessageType,
)

_log = getLogger("NapcatApi")


@dataclass
class NapcatConfig:
    """Napcat 客户端配置

    Attributes:
        url: WebSocket 连接地址
        token: 认证 Token（可选）
        heartbeat: 心跳间隔（秒）
        reconnect_attempts: 重连尝试次数
        receive_timeout: 接收超时时间（秒）
        ready_timeout: 首次连接就绪超时（秒）
    """

    url: str
    """WebSocket 连接地址"""
    token: str | None = None
    """认证 Token（可选）"""
    heartbeat: float = 30.0
    """心跳间隔（秒）"""
    reconnect_attempts: int = 5
    """重连尝试次数"""
    receive_timeout: float = 60.0
    """接收超时时间（秒）"""
    ready_timeout: float = 30.0
    """首次连接就绪超时（秒）"""

    def __post_init__(self) -> None:
        if self.ready_timeout <= 0:
            raise ValueError("ready_timeout 必须大于 0")


class NapcatClient:
    """Napcat WebSocket 客户端，用于与 Napcat QQ Bot 进行通信"""

    @classmethod
    def create(cls, config: NapcatConfig) -> "NapcatClient":
        """从配置创建 NapcatClient 实例

        Args:
            config: napcat 配置
        """
        napcat_config: NapcatConfig = config
        headers = {}

        if napcat_config.token:
            headers["Authorization"] = napcat_config.token

        return cls(
            url=napcat_config.url,
            headers=headers,
            heartbeat=napcat_config.heartbeat,
            reconnect_attempts=napcat_config.reconnect_attempts,
            receive_timeout=napcat_config.receive_timeout,
            ready_timeout=napcat_config.ready_timeout,
        )

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        heartbeat: float = 30.0,
        reconnect_attempts: int = 5,
        receive_timeout: float = 60.0,
        ready_timeout: float = 30.0,
    ):
        """初始化 Napcat 客户端

        Args:
            url: WebSocket 连接地址
            headers: 请求头，通常包含 Authorization
            heartbeat: 心跳间隔
            reconnect_attempts: 重连尝试次数
            receive_timeout: 接收超时时间
            ready_timeout: 首次连接就绪超时
        """
        self.url = url
        self._handler: Callable[[dict[str, Any]], Awaitable[None]] | None = None
        self.timeout = receive_timeout
        self.ready_timeout = ready_timeout
        self.client = AsyncWebSocketClient(
            uri=url,
            logger=_log,
            headers=headers or {},
            heartbeat=heartbeat,
            reconnect_attempts=reconnect_attempts,
            receive_timeout=receive_timeout,
        )
        self._task: asyncio.Task | None = None
        self._listener_id: ListenerId | None = None
        self._pending_requests: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._running = False
        self._transport_cleanup_required = False
        self._lifecycle_lock = asyncio.Lock()
        self._health_handler: Callable[[ConnectionHealth], None] | None = None
        self.client.set_health_handler(self._handle_transport_health)

    @property
    def pending_requests(self) -> int:
        """当前等待 echo 响应的请求数量."""
        return len(self._pending_requests)

    @property
    def running(self) -> bool:
        """客户端已完成启动且传输主任务仍在运行."""
        return self._running and self.client.running

    @property
    def ready(self) -> bool:
        """WebSocket 当前已就绪."""
        return self.running and self.client.ready

    @property
    def cleanup_required(self) -> bool:
        """是否仍持有消息任务、监听器或传输层清理责任."""
        return (
            self._transport_cleanup_required
            or self._listener_id is not None
            or self._task is not None
        )

    def set_handler(self, handler: Callable[[dict[str, Any]], Awaitable[None]]):
        """设置消息处理函数

        Args:
            handler: 消息处理函数，必须是异步函数，接受一个 dict 参数
        """
        if not asyncio.iscoroutinefunction(handler):
            raise TypeError("handler must be an async function")
        self._handler = handler

    def set_health_handler(
        self,
        handler: Callable[[ConnectionHealth], None] | None,
    ) -> None:
        """设置上层 Source 的连接健康观察者."""
        self._health_handler = handler

    async def start(self):
        """事务化启动客户端，返回时首次连接已就绪."""
        if not self._handler:
            raise RuntimeError(
                "消息处理函数未设置，请先调用 set_handler() 设置处理函数"
            )
        async with self._lifecycle_lock:
            if self.running and self.ready and self._task is not None:
                return
            if self.cleanup_required:
                await self._stop_locked()

            try:
                # 先创建监听器，确保握手后立即到达的消息不会落在窗口期。
                self._listener_id = await self.client.create_listener()
                self._transport_cleanup_required = True
                await self.client.start(wait_ready=False)
                self._task = asyncio.create_task(self._process_messages())
                await self.client.wait_until_ready(timeout=self.ready_timeout)
            except BaseException as start_error:
                try:
                    await self._stop_locked()
                except BaseException as cleanup_error:
                    if cleanup_error is not start_error:
                        start_error.add_note(
                            "NapcatClient 启动回滚失败: %s: %s"
                            % (type(cleanup_error).__name__, cleanup_error)
                        )
                raise

            self._running = True
            _log.info("Napcat client started with listener: %s", self._listener_id)

    async def stop(self):
        """停止客户端（幂等，可被 on_stop 与 ApiRegistry.aclose_all 重复调用）"""
        async with self._lifecycle_lock:
            await self._stop_locked()

    async def _stop_locked(self) -> None:
        """尽力释放所有内部资源，保留失败步骤的句柄以便重试."""
        self._running = False
        pending = list(self._pending_requests.values())
        self._pending_requests.clear()
        for future in pending:
            if not future.done():
                future.cancel()

        first_error: BaseException | None = None
        task = self._task
        if task is not None:
            try:
                if not task.done():
                    task.cancel()
                await task
            except asyncio.CancelledError as exc:
                if not task.cancelled():
                    first_error = exc
            except BaseException as exc:
                first_error = exc
            finally:
                if task.done():
                    self._task = None

        listener_id = self._listener_id
        if listener_id is not None:
            try:
                await self.client.remove_listener(listener_id)
            except BaseException as exc:
                first_error = self._merge_cleanup_error(first_error, exc)
            else:
                self._listener_id = None

        needs_transport_stop = self._transport_cleanup_required or bool(pending)
        if needs_transport_stop:
            try:
                await self.client.stop()
            except BaseException as exc:
                first_error = self._merge_cleanup_error(first_error, exc)
            else:
                self._transport_cleanup_required = False

        if first_error is not None:
            raise first_error

        _log.info("Napcat client stopped")

    @staticmethod
    def _merge_cleanup_error(
        first: BaseException | None,
        current: BaseException,
    ) -> BaseException:
        """保留第一个清理异常，并把后续失败附加到诊断注释."""
        if first is None:
            return current
        if current is not first:
            first.add_note(
                "NapcatClient 后续清理失败: %s: %s" % (type(current).__name__, current)
            )
        return first

    def _handle_transport_health(self, health: ConnectionHealth) -> None:
        """把传输层健康变化转发给 Source."""
        handler = self._health_handler
        if handler is not None:
            handler(health)

    async def send_request(self, message: dict) -> dict | None:
        """发送请求到服务器

        Args:
            message: 请求内容，Dict
        """
        echo = str(uuid4())
        payload = dict(message)
        payload["echo"] = echo
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[echo] = future

        try:
            _log.debug("发送请求: action=%s, echo=%s", payload.get("action"), echo)
            await self.client.send(payload)
            _log.debug("发送请求%s", echo)
            return await asyncio.wait_for(future, timeout=self.timeout)
        except asyncio.CancelledError:
            _log.debug("请求 %s 被取消", echo)
            raise
        finally:
            registered = self._pending_requests.pop(echo, None)
            if registered is not None and not registered.done():
                registered.cancel()

    def _resolve_response(self, data: dict[str, Any]) -> bool:
        """按 echo 将响应投递给对应请求.

        Returns:
            找到仍在等待的请求并完成其 Future 时返回 ``True``。
        """
        echo = data.get("echo")
        if echo is None:
            return False
        future = self._pending_requests.get(str(echo))
        if future is None or future.done():
            return False
        future.set_result(data)
        return True

    async def _get_message(
        self, listener_id: ListenerId | None = None
    ) -> tuple[Any, MessageType]:
        """获取一条消息（阻塞）
        Returns:
            (消息内容, 消息类型) 元组
        """
        _listener_id = self._listener_id if listener_id is None else listener_id
        assert _listener_id is not None, "Listener not available"
        return await self.client.get_message(_listener_id, self.timeout)

    async def _process_messages(self):
        """持续处理消息（事件循环）"""
        _log.info("Started processing messages")

        try:
            while self.client.running:
                try:
                    message, msg_type = await self._get_message()

                    if msg_type == MessageType.Text:
                        # 解析 JSON 消息
                        try:
                            data: dict = json.loads(message)
                            if data.get("echo") is not None:
                                if not self._resolve_response(data):
                                    _log.debug(
                                        "收到无等待者的响应: echo=%s", data.get("echo")
                                    )
                                # 带 echo 的响应不进入事件 handler
                                continue
                            _log.debug(data)
                            # noinspection PyCallingNonCallable
                            assert self._handler is not None
                            await self._handler(
                                data
                            )  # post_type: ignore (运行时设置 handler)
                        except json.JSONDecodeError:
                            _log.error("Failed to parse message: %s", message)
                        except Exception as e:
                            _log.error("Handler error: %s", e)
                    elif msg_type == MessageType.Close:
                        _log.warning("Received close message")
                        break

                except TimeoutError:
                    # 超时是正常的，继续等待
                    continue
                except (ListenerClosedError, ListenerEvictedError) as e:
                    # 监听器已关闭或被驱逐：这条 while 再转下去只会立刻拿到
                    # 同一个异常，变成不带任何 sleep 的 100% CPU 空转。
                    _log.warning("监听器不可用，停止消息处理: %s", e)
                    break
                except Exception as e:
                    _log.error("Error processing message: %s", e)
        except asyncio.CancelledError:
            # 任务被取消（stop() 调用），优雅退出
            _log.info("Message processing stopped")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.stop()


class NapcatApi(BaseApi):
    """Napcat API，提供与 Napcat QQ Bot 交互的接口"""

    @classmethod
    def create(cls, ctx: ApiRegistry, config_key: str = "napcat") -> "NapcatApi":
        """
        从上下文创建 NapcatApi 实例
        Args:
            ctx: API 上下文
            config_key: 配置键

        Raises:
            ConfigError: 缺少 ``config_key`` 对应的 napcat 配置。
                napcat 必须有 url/token 才能连接，配置缺失时用 require_config
                直接报错，而不是把 None 一路带到深处变成
                ``AttributeError: 'NoneType' object has no attribute 'token'``。
        """
        return cls(ctx.require_config(config_key))

    def __init__(self, config: NapcatConfig):
        self.client = NapcatClient.create(config)

    async def aclose(self) -> None:
        """释放 WebSocket 连接与后台任务（由 ApiRegistry.aclose_all 调用）."""
        await self.client.stop()

    def set_handler(self, handler: Callable[[dict[str, Any]], Awaitable[None]]):
        """设置消息处理函数"""
        self.client.set_handler(handler)

    def set_health_handler(
        self,
        handler: Callable[[ConnectionHealth], None] | None,
    ) -> None:
        """设置连接健康观察者."""
        self.client.set_health_handler(handler)

    async def start(self):
        """启动客户端"""
        await self.client.start()

    async def stop(self):
        """停止客户端"""
        await self.client.stop()

    def get_metrics(self) -> dict:
        """获取客户端指标"""
        return self.client.client.get_metrics()

    async def send_request(self, message: dict) -> dict | None:
        """发送请求到服务器"""
        return await self.client.send_request(message)

    # ================== 业务接口 ================== #

    async def send_group_message(
        self, group_id: int, message: list[dict]
    ) -> dict | None:
        """发送群消息"""
        results = await self.send_request(
            {
                "action": "send_group_msg",
                "params": {"group_id": group_id, "message": message},
            }
        )
        return results
