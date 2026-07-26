import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from logging import getLogger
from typing import Any
from uuid import uuid4

from bilipy_bot.core.api import BaseApi
from bilipy_bot.core.context import ApiRegistry
from bilipy_bot.utils import AsyncWebSocketClient, ListenerId, MessageType
from bilipy_bot.utils.websocket import ListenerClosedError, ListenerEvictedError

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
        )

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        heartbeat: float = 30.0,
        reconnect_attempts: int = 5,
        receive_timeout: float = 60.0,
    ):
        """初始化 Napcat 客户端

        Args:
            url: WebSocket 连接地址
            headers: 请求头，通常包含 Authorization
            heartbeat: 心跳间隔
            reconnect_attempts: 重连尝试次数
            receive_timeout: 接收超时时间
        """
        self.url = url
        self._handler: Callable[[dict[str, Any]], Awaitable[None]] | None = None
        self.timeout = receive_timeout
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

    @property
    def pending_requests(self) -> int:
        """当前等待 echo 响应的请求数量."""
        return len(self._pending_requests)

    def set_handler(self, handler: Callable[[dict[str, Any]], Awaitable[None]]):
        """设置消息处理函数

        Args:
            handler: 消息处理函数，必须是异步函数，接受一个 dict 参数
        """
        if not asyncio.iscoroutinefunction(handler):
            raise TypeError("handler must be an async function")
        self._handler = handler

    async def start(self):
        """启动客户端并创建监听器"""
        if not self._handler:
            raise RuntimeError(
                "消息处理函数未设置，请先调用 set_handler() 设置处理函数"
            )
        await self.client.start()
        self._listener_id = await self.client.create_listener()
        self._task = asyncio.create_task(self._process_messages())
        _log.info("Napcat client started with listener: %s", self._listener_id)

    async def stop(self):
        """停止客户端（幂等，可被 on_stop 与 ApiRegistry.aclose_all 重复调用）"""
        pending = list(self._pending_requests.values())
        self._pending_requests.clear()
        for future in pending:
            if not future.done():
                future.cancel()

        task = self._task
        self._task = None
        if task and not task.done():
            try:
                task.cancel()
                await task
            except asyncio.CancelledError:
                # 任务被取消是预期行为，忽略异常
                pass

        listener_id = self._listener_id
        self._listener_id = None
        if listener_id:
            await self.client.remove_listener(listener_id)

        await self.client.stop()
        _log.info("Napcat client stopped")

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
