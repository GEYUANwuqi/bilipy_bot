import abc
from enum import Enum
from typing import Any, Dict, NewType, Optional, Tuple, Union

# ------------------- 抽象层 -------------------
ListenerId = NewType("ListenerId", str)


class MessageType(Enum):
    Text = "text"
    Binary = "binary"
    Ping = "ping"
    Pong = "pong"
    Close = "close"
    Error = "error"
    NONE = "none"


class WebSocketState(Enum):
    Disconnected = "disconnected"
    Connecting = "connecting"
    CONNECTED = "connected"
    Rconnecting = "reconnecting"
    Closing = "closing"
    Closed = "closed"


class WebSocketError(Exception):
    pass


class ConnectionError(WebSocketError):
    pass


class ListenerEvictedError(WebSocketError):
    pass


class ListenerClosedError(WebSocketError):
    pass


class ABCWebSocketClient(abc.ABC):
    """WebSocket 客户端抽象，任何实现都必须满足这些接口。"""

    @abc.abstractmethod
    async def start(self) -> None:
        """启动客户端（连接、重连、收发任务）。"""
        raise NotImplementedError

    @abc.abstractmethod
    async def stop(self) -> None:
        """优雅停止：关闭连接、清理资源。"""
        raise NotImplementedError

    @abc.abstractmethod
    async def create_listener(self, buffer_size: Optional[int] = None) -> ListenerId:
        """创建消息监听器，返回其 ID。"""
        raise NotImplementedError

    @abc.abstractmethod
    async def remove_listener(self, listener_id: ListenerId) -> None:
        """移除指定监听器。"""
        raise NotImplementedError

    @abc.abstractmethod
    async def send(self, message: Union[str, bytes, Dict]) -> None:
        """异步发送一条消息。"""
        raise NotImplementedError

    @abc.abstractmethod
    async def get_message(
        self, listener_id: ListenerId, timeout: Optional[float] = None
    ) -> Tuple[Any, MessageType]:
        """从指定监听器阻塞读取一条消息。"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_message_nowait(
        self, listener_id: ListenerId
    ) -> Optional[Tuple[Any, MessageType]]:
        """非阻塞读取；无数据返回 None。"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """返回客户端运行时指标（同步即刻返回）。"""
        raise NotImplementedError

    # 可选：异步上下文管理器协议
    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
