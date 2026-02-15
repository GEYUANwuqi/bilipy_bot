import asyncio
import json
from typing import Optional, Any, Callable, Awaitable
from logging import getLogger
from dataclasses import dataclass
from uuid import uuid4

from manager.context import APIContext
from api.base_api import BaseApi
from utils.wsclient import AsyncWebSocketClient, MessageType, ListenerId

_log = getLogger("NapcatApi")


@dataclass
class NapcatConfig:
    """Napcat 客户端配置"""
    uri: str
    """WebSocket 连接地址"""
    token: Optional[str] = None
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
            uri=napcat_config.uri,
            headers=headers,
            heartbeat=napcat_config.heartbeat,
            reconnect_attempts=napcat_config.reconnect_attempts,
            receive_timeout=napcat_config.receive_timeout
        )

    def __init__(
        self,
        uri: str,
        headers: Optional[dict[str, str]] = None,
        heartbeat: float = 30.0,
        reconnect_attempts: int = 5,
        receive_timeout: float = 60.0
    ):
        """初始化 Napcat 客户端

        Args:
            uri: WebSocket 连接地址
            headers: 请求头，通常包含 Authorization
            heartbeat: 心跳间隔
            reconnect_attempts: 重连尝试次数
            receive_timeout: 接收超时时间
        """
        self.uri = uri
        self._handler: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None
        self.timeout = receive_timeout
        self.client = AsyncWebSocketClient(
            uri=uri,
            logger=_log,
            headers=headers or {},
            heartbeat=heartbeat,
            reconnect_attempts=reconnect_attempts,
            receive_timeout=receive_timeout
        )
        self._task: Optional[asyncio.Task] = None
        self._listener_id: Optional[ListenerId] = None

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
            raise RuntimeError("消息处理函数未设置，请先调用 set_handler() 设置处理函数")
        await self.client.start()
        self._listener_id = await self.client.create_listener()
        self._task = asyncio.create_task(self._process_messages())
        _log.info(f"Napcat client started with listener: {self._listener_id}")

    async def stop(self):
        """停止客户端"""
        if self._task and not self._task.done():
            try:
                self._task.cancel()
                await self._task
            except asyncio.CancelledError:
                # 任务被取消是预期行为，忽略异常
                pass

        if self._listener_id:
            await self.client.remove_listener(self._listener_id)

        await self.client.stop()
        _log.info("Napcat client stopped")

    async def send_request(self, message: dict) -> Optional[dict]:
        """发送请求到服务器

        Args:
            message: 请求内容，Dict
        """
        _log.debug(f"Sent message: {message}")
        echo = str(uuid4())
        message["echo"] = echo
        await self.client.send(message)
        _log.debug(f"发送请求{echo}")

        try:
            while True:
                #  等待响应，直到收到带有相同 echo 的消息
                message, t = await self._get_message()
                match t:
                    case MessageType.Text:
                        try:
                            results: dict = json.loads(message)
                        except json.JSONDecodeError as e:
                            _log.error(f"解析错误: {e}")
                            return None
                        if results.get("echo") == echo:
                            return results
                    case _:
                        _log.debug(f"未知类型返回: {t}, 内容: {message}")
                        return None
        except asyncio.CancelledError:
            _log.debug(f"请求 {echo} 被取消")
            raise

    async def _get_message(self) -> tuple[Any, MessageType]:
        """获取一条消息（阻塞）
        Returns:
            (消息内容, 消息类型) 元组
        """
        return await self.client.get_message(self._listener_id, self.timeout)

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
                            if data.get("echo", 0):
                                # 跳过带有 echo 的消息，这些是请求的响应，不需要处理
                                break
                            _log.debug(data)
                            # noinspection PyCallingNonCallable
                            await self._handler(data)  # post_type: ignore (运行时设置 handler)
                        except json.JSONDecodeError:
                            _log.error(f"Failed to parse message: {message}")
                        except Exception as e:
                            _log.error(f"Handler error: {e}")
                    elif msg_type == MessageType.Close:
                        _log.warning("Received close message")
                        break

                except asyncio.TimeoutError:
                    # 超时是正常的，继续等待
                    continue
                except Exception as e:
                    _log.error(f"Error processing message: {e}")
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
    def create(cls, ctx: APIContext) -> "NapcatApi":
        """
        从上下文创建 NapcatApi 实例
        Args:
            ctx: API 上下文
        """
        return cls(
            ctx.config.get_config("napcat")
        )

    def __init__(self, config: NapcatConfig):
        self.client = NapcatClient.create(config)

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

    async def send_request(self, message: dict) -> Optional[dict]:
        """发送请求到服务器"""
        return await self.client.send_request(message)

    async def send_group_message(self, group_id: int, message: list[dict]) -> Optional[dict]:
        """发送群消息"""
        results = await self.send_request({
            "action": "send_group_msg",
            "params": {
                "group_id": group_id,
                "message": message
            }
        })
        return results
