import asyncio
import json
from typing import Optional, Dict, Any, Callable
from logging import getLogger

from api.context import APIContext
from api.base_api import BaseApi
from api.wsclient import AsyncWebSocketClient
from api.abc import MessageType, ListenerId

_log = getLogger("NapcatClient")


class NapcatClient(BaseApi):
    """Napcat WebSocket 客户端，用于与 Napcat QQ Bot 进行通信"""

    @classmethod
    def create(cls, ctx: APIContext) -> "NapcatClient":
        """从配置创建 NapcatClient 实例

        配置项:
            napcat_uri: WebSocket URI (必需)
            napcat_token: 认证 Token (可选)
            napcat_heartbeat: 心跳间隔，默认 30.0 秒
            napcat_reconnect_attempts: 重连次数，默认 5 次
        """
        uri = ctx.config.get_config("napcat_uri")
        token = ctx.config.get_config("napcat_token")
        heartbeat = ctx.config.get_config("napcat_heartbeat", 30.0)
        reconnect_attempts = ctx.config.get_config("napcat_reconnect_attempts", 5)

        if not uri:
            raise ValueError("napcat_uri is required in config")

        headers = {}
        if token:
            headers["Authorization"] = token

        return cls(
            uri=uri,
            headers=headers,
            heartbeat=heartbeat,
            reconnect_attempts=reconnect_attempts
        )

    def __init__(
        self,
        uri: str,
        headers: Optional[Dict[str, str]] = None,
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
        self.client = AsyncWebSocketClient(
            uri=uri,
            logger=_log,
            headers=headers or {},
            heartbeat=heartbeat,
            reconnect_attempts=reconnect_attempts,
            receive_timeout=receive_timeout
        )
        self._listener_id: Optional[ListenerId] = None
        self._message_handlers: Dict[str, Callable] = {}

    async def start(self):
        """启动客户端并创建监听器"""
        await self.client.start()
        self._listener_id = await self.client.create_listener()
        _log.info(f"Napcat client started with listener: {self._listener_id}")

    async def stop(self):
        """停止客户端"""
        if self._listener_id:
            await self.client.remove_listener(self._listener_id)
        await self.client.stop()
        _log.info("Napcat client stopped")

    async def get_message(self, timeout: Optional[float] = None) -> tuple[Any, MessageType]:
        """获取一条消息（阻塞）

        Args:
            timeout: 超时时间（秒），None 表示永久等待

        Returns:
            (消息内容, 消息类型) 元组
        """
        if not self._listener_id:
            raise RuntimeError("Client not started, call start() first")

        return await self.client.get_message(self._listener_id, timeout)

    def register_handler(self, event_type: str, handler: Callable):
        """注册消息处理器

        Args:
            event_type: 事件类型，如 'message', 'notice', 'request'
            handler: 处理函数，接收消息字典作为参数
        """
        self._message_handlers[event_type] = handler

    async def process_messages(self):
        """持续处理消息（事件循环）"""
        _log.info("Started processing messages")

        while self.client.running:
            try:
                message, msg_type = await self.get_message(timeout=1.0)

                if msg_type == MessageType.Text:
                    # 解析 JSON 消息
                    try:
                        data = json.loads(message) if isinstance(message, str) else message
                        await self._dispatch_message(data)
                    except json.JSONDecodeError:
                        _log.error(f"Failed to parse message: {message}")
                elif msg_type == MessageType.Close:
                    _log.warning("Received close message")
                    break

            except asyncio.TimeoutError:
                # 超时是正常的，继续等待
                continue
            except Exception as e:
                _log.error(f"Error processing message: {e}")

    async def _dispatch_message(self, data: Dict):
        """分发消息到对应的处理器

        Args:
            data: 解析后的消息数据
        """
        # Napcat 消息格式示例:
        # {"post_type": "message", "message_type": "group", ...}
        post_type = data.get("post_type")

        if post_type and post_type in self._message_handlers:
            handler = self._message_handlers[post_type]
            try:
                await handler(data)
            except Exception as e:
                _log.error(f"Handler error for {post_type}: {e}")
        else:
            _log.debug(f"No handler for message type: {post_type}")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.stop()
