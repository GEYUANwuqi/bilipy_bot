# @Author Fish.zh@outlook.com
# @Version 1.1
import asyncio
import json
import logging
import random
import threading
import time
import uuid
from asyncio import QueueEmpty, QueueFull
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NewType, cast

import aiohttp
from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType

ListenerId = NewType("ListenerId", str)


class MessageType(Enum):
    """WebSocket 消息类型枚举"""

    Text = "text"
    Binary = "binary"
    Ping = "ping"
    Pong = "pong"
    Close = "close"
    Error = "error"
    NONE = "none"


class WebSocketState(Enum):
    """WebSocket 连接状态枚举"""

    Disconnected = "disconnected"
    Connecting = "connecting"
    CONNECTED = "connected"
    Rconnecting = "reconnecting"
    Closing = "closing"
    Closed = "closed"


class ConnectionHealthState(str, Enum):
    """WebSocket 客户端对外暴露的连接健康状态."""

    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPING = "stopping"


@dataclass(frozen=True, slots=True)
class ConnectionHealth:
    """不携带异常对象的 WebSocket 连接健康快照."""

    state: ConnectionHealthState
    last_success_at: float | None
    last_error_at: float | None
    last_error_type: str | None
    last_error_message: str | None


class WebSocketError(Exception):
    """WebSocket 基础异常"""

    pass


class ConnectionError(WebSocketError):
    """连接相关异常"""

    pass


class ListenerEvictedError(WebSocketError):
    """监听器被驱逐异常"""

    pass


class ListenerClosedError(WebSocketError):
    """监听器已关闭异常"""

    pass


@dataclass
class WebSocketConfig:
    """WebSocket 配置类

    包含 WebSocket 连接的所有配置参数，包括连接超时、重连策略、
    压缩设置、监听器限制等。

    Attributes:
        uri: WebSocket 服务器地址，必须以 ws:// 或 wss:// 开头
        headers: 连接请求头字典
        heartbeat: 心跳间隔（秒），默认 30.0
        receive_timeout: 接收消息超时时间（秒），默认 60.0
        reconnect_attempts: 最大重连次数，默认 5，0 表示无限重连
        connect_timeout: 连接超时时间（秒），默认 20.0
        send_queue_size: 发送队列大小，默认 1024
        session_timeout: 会话总超时时间（秒），默认 300.0
        backoff_base: 退避基数（秒），默认 1.0
        backoff_max: 最大退避时间（秒），默认 600.0
        jitter_factor: 抖动因子，默认 5.0
        compression: 压缩级别 0-15，默认 15，0 表示不压缩
        verify_ssl: 是否验证 SSL 证书，默认 True
        max_listeners: 最大监听器数量，默认 1000
        listener_buffer_size: 每个监听器的缓冲区大小，默认 100
    """

    uri: str
    headers: dict[str, str] = field(default_factory=dict)
    heartbeat: float = 30.0
    receive_timeout: float = 60.0
    reconnect_attempts: int = 5
    connect_timeout: float = 20.0
    send_queue_size: int = 1024
    session_timeout: float = 300.0
    backoff_base: float = 1.0
    backoff_max: float = 600.0
    jitter_factor: float = 5
    compression: int = 15
    verify_ssl: bool = True
    max_listeners: int = 1000
    listener_buffer_size: int = 100

    def __post_init__(self):
        """配置验证

        Raises:
            ValueError: URI 格式不正确或配置参数无效时抛出
        """
        if not self.uri.startswith(("ws://", "wss://")):
            raise ValueError("URI must start with ws:// or wss://")
        if self.heartbeat <= 0:
            raise ValueError("Heartbeat must be positive")
        if self.receive_timeout <= 0:
            raise ValueError("Receive timeout must be positive")
        if self.reconnect_attempts < 0:
            raise ValueError("Reconnect attempts cannot be negative")
        if self.connect_timeout <= 0:
            raise ValueError("Connect timeout must be positive")
        if self.send_queue_size <= 0:
            raise ValueError("Send queue size must be positive")
        if self.session_timeout <= 0:
            raise ValueError("Session timeout must be positive")
        if self.backoff_base < 0:
            raise ValueError("Backoff base cannot be negative")
        if self.backoff_max < self.backoff_base:
            raise ValueError("Backoff max cannot be less than backoff base")
        if self.jitter_factor < 0:
            raise ValueError("Jitter factor cannot be negative")
        if not 0 <= self.compression <= 15:
            raise ValueError("Compression must be between 0 and 15")
        if self.max_listeners <= 0:
            raise ValueError("Max listeners must be positive")
        if self.listener_buffer_size <= 0:
            raise ValueError("Listener buffer size must be positive")


_CLOSE_SENTINEL = object()
"""放入监听器队列的关闭哨兵.

``close()`` 需要唤醒已经阻塞在 ``queue.get()`` 上的消费者——只置标志位的话，
等待者会永远挂在那里等一条永不到来的消息。哨兵被 ``get()`` 识别后转换为
``ListenerClosedError``，因此不会被误当成业务消息。
"""

_NO_INFLIGHT_MESSAGE = object()
_SendMessage = str | bytes | dict[str, Any]


class WebSocketListener:
    """WebSocket 消息监听器

    为每个订阅者提供独立的消息队列，支持异步迭代和超时控制。
    当队列满时自动丢弃最旧的消息。

    Attributes:
        id: 监听器唯一标识符
        queue: 消息队列
        created_at: 创建时间戳
    """

    def __init__(self, buffer_size: int = 100):
        """初始化监听器

        Args:
            buffer_size: 消息队列缓冲区大小，默认 100
        """
        self.id = ListenerId(str(uuid.uuid4()))
        self.queue = asyncio.Queue(maxsize=buffer_size)
        self.created_at = time.time()
        self._closed = False

    async def put(self, message: Any, msg_type: MessageType) -> bool:
        """放入消息到队列

        如果队列已满，自动丢弃最旧的消息以腾出空间。

        Args:
            message: 消息内容
            msg_type: 消息类型

        Returns:
            bool: 放入成功返回 True，失败返回 False
        """
        if self._closed:
            return False

        try:
            self.queue.put_nowait((message, msg_type))
            return True
        except QueueFull:
            # 队列满时丢弃最旧的消息
            try:
                self.queue.get_nowait()  # 丢弃一个旧消息
                self.queue.put_nowait((message, msg_type))  # 放入新消息
                return True
            except QueueFull:
                return False

    async def get(self, timeout: float | None = None) -> tuple[Any, MessageType]:
        """获取消息（阻塞）

        Args:
            timeout: 超时时间（秒），None 表示无限等待

        Returns:
            Tuple[Any, MessageType]: 消息内容和类型

        Raises:
            ListenerClosedError: 监听器已关闭时抛出
            asyncio.TimeoutError: 超时时抛出
            asyncio.CancelledError: 任务被取消时抛出
        """
        if self._closed:
            raise ListenerClosedError("Listener %s is closed" % self.id)

        try:
            if timeout is None:
                item = await self.queue.get()
            else:
                item = await asyncio.wait_for(self.queue.get(), timeout=timeout)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if self._closed:
                raise ListenerClosedError("Listener %s is closed" % self.id) from e
            raise

        if item[0] is _CLOSE_SENTINEL:
            # 等待期间监听器被关闭：把哨兵放回去，让其他等待者也能醒
            self._requeue_close_sentinel()
            raise ListenerClosedError("Listener %s is closed" % self.id)
        return item

    def get_nowait(self) -> tuple[Any, MessageType] | None:
        """非阻塞获取消息

        Returns:
            Optional[Tuple[Any, MessageType]]: 消息内容和类型，无数据时返回 None

        Raises:
            ListenerClosedError: 监听器已关闭时抛出
        """
        if self._closed:
            raise ListenerClosedError("Listener %s is closed" % self.id)

        try:
            item = self.queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

        if item[0] is _CLOSE_SENTINEL:
            self._requeue_close_sentinel()
            raise ListenerClosedError("Listener %s is closed" % self.id)
        return item

    def _requeue_close_sentinel(self) -> None:
        """把关闭哨兵放回队列，使后续/并发的等待者同样会醒来."""
        try:
            self.queue.put_nowait((_CLOSE_SENTINEL, MessageType.Close))
        except QueueFull:
            pass

    def close(self) -> None:
        """关闭监听器，清空队列并唤醒所有等待者

        幂等。清空积压消息后放入关闭哨兵——只置 ``_closed`` 标志的话，
        已经阻塞在 ``get()`` 上的消费者不会被唤醒，会一直挂着。
        """
        if self._closed:
            return
        self._closed = True
        # 清空队列以释放等待的消费者
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._requeue_close_sentinel()

    @property
    def is_closed(self) -> bool:
        """检查监听器是否已关闭

        Returns:
            bool: 已关闭返回 True，否则返回 False
        """
        return self._closed

    def __aiter__(self):
        """返回异步迭代器"""
        return self

    async def __anext__(self):
        """异步迭代下一个消息

        Returns:
            Tuple[Any, MessageType]: 消息内容和类型

        Raises:
            StopAsyncIteration: 监听器关闭时抛出
        """
        try:
            return await self.get()
        except ListenerClosedError:
            raise StopAsyncIteration


class AioHttpWebSocketConnection:
    """基于 aiohttp 的 WebSocket 连接管理

    负责底层的 WebSocket 连接建立、消息收发和资源清理。
    自动处理压缩协商失败等边界情况。

    Attributes:
        config: WebSocket 配置对象
        logger: 日志记录器
        websocket: aiohttp WebSocket 响应对象
        session: aiohttp 客户端会话
        state: 当前连接状态
        metrics: 连接指标统计
    """

    def __init__(self, config: WebSocketConfig, logger: logging.Logger):
        """初始化连接管理器

        Args:
            config: WebSocket 配置对象
            logger: 日志记录器实例
        """
        self.config = config
        self.logger = logger

        self.websocket: ClientWebSocketResponse | None = None
        self.session: ClientSession | None = None
        self.state = WebSocketState.Disconnected

        # 指标
        self.metrics = {
            "connection_attempts": 0,
            "successful_connections": 0,
            "failed_connections": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "errors": 0,
        }

    async def connect(self) -> None:
        """建立 WebSocket 连接

        如果已经处于连接中或已连接状态，直接返回。
        支持自动处理压缩协商失败的情况。

        Raises:
            ConnectionError: 连接失败时抛出
        """
        if self.state in [WebSocketState.Connecting, WebSocketState.CONNECTED]:
            return

        self.state = WebSocketState.Connecting
        self.metrics["connection_attempts"] += 1
        self.logger.info("Connecting to %s", self.config.uri)

        try:
            # 创建 aiohttp 会话
            timeout = aiohttp.ClientTimeout(
                total=self.config.session_timeout,
                connect=self.config.connect_timeout,
                sock_connect=self.config.connect_timeout,
                sock_read=self.config.receive_timeout,
            )

            self.session = ClientSession(timeout=timeout)

            # 建立 WebSocket 连接
            self.websocket = await self.session.ws_connect(
                self.config.uri,
                headers=self.config.headers,
                heartbeat=self.config.heartbeat,
                compress=self.config.compression,
                verify_ssl=self.config.verify_ssl,
            )

            self.state = WebSocketState.CONNECTED
            self.metrics["successful_connections"] += 1
            self.logger.info("Connected to %s", self.config.uri)

        except Exception as e:
            self.state = WebSocketState.Disconnected
            self.metrics["failed_connections"] += 1

            # 清理资源
            if self.session:
                await self.session.close()
                self.session = None

            self.logger.error("Connection failed: %s, error: %s", self.config.uri, e)
            if "wbits=" in str(e):
                self.logger.error("Detected zlib wbits compression error")
                if self.config.compression > 0:
                    self.logger.info("Enabled compression reconnection")
                    self.config.compression = 15
                else:
                    self.logger.info("Disable compression reconnection")
                    self.config.compression = 0

            raise ConnectionError("Connection failed: %s" % e) from e

    async def close(self) -> None:
        """关闭 WebSocket 连接并清理资源"""
        if self.state == WebSocketState.Closed:
            return

        self.state = WebSocketState.Closing
        self.logger.debug("Closing connection")

        try:
            if self.websocket:
                await self.websocket.close()
        except Exception as e:
            self.logger.error("WebSocket close error: %s", e)

        try:
            if self.session:
                await self.session.close()
        except Exception as e:
            self.logger.error("Session close error: %s", e)
        finally:
            self.websocket = None
            self.session = None
            self.state = WebSocketState.Closed
            self.logger.info("Connection closed")

    async def send(self, message: str | bytes | dict) -> None:
        """发送消息

        Args:
            message: 要发送的消息，支持字符串、字节或字典（自动转为 JSON）

        Raises:
            ConnectionError: 未连接时抛出
            Exception: 发送失败时抛出
        """
        if self.state != WebSocketState.CONNECTED or not self.websocket:
            raise ConnectionError("Not connected")

        try:
            # 格式化消息
            if isinstance(message, dict):
                formatted = json.dumps(message)
            elif isinstance(message, bytes):
                formatted = message
            else:
                formatted = str(message)

            # 发送消息
            if isinstance(formatted, str):
                await self.websocket.send_str(formatted)
            else:
                await self.websocket.send_bytes(formatted)

            self.metrics["messages_sent"] += 1
            self.metrics["bytes_sent"] += len(formatted)

        except Exception as e:
            self.metrics["errors"] += 1
            self.logger.error("Send error: %s", e)
            raise

    async def receive(self) -> tuple[Any, MessageType]:
        """接收消息

        Returns:
            Tuple[Any, MessageType]: 消息数据和类型

        Raises:
            ConnectionError: 未连接时抛出
            asyncio.TimeoutError: 接收超时时抛出
            Exception: 接收失败时抛出
        """
        if self.state != WebSocketState.CONNECTED or not self.websocket:
            raise ConnectionError("Not connected")

        try:
            # 接收消息
            msg = await self.websocket.receive(timeout=self.config.receive_timeout)

            # 处理不同类型的消息
            if msg.type == WSMsgType.TEXT:
                self.metrics["messages_received"] += 1
                self.metrics["bytes_received"] += len(msg.data)
                return msg.data, MessageType.Text

            elif msg.type == WSMsgType.BINARY:
                self.metrics["messages_received"] += 1
                self.metrics["bytes_received"] += len(msg.data)
                return msg.data, MessageType.Binary

            elif msg.type == WSMsgType.PING:
                return msg.data, MessageType.Ping

            elif msg.type == WSMsgType.PONG:
                return msg.data, MessageType.Pong

            elif msg.type == WSMsgType.CLOSE:
                return msg.data, MessageType.Close

            elif msg.type == WSMsgType.ERROR:
                self.metrics["errors"] += 1
                self.logger.error("WebSocket error: %s", msg.data)
                return msg.data, MessageType.Error

            else:
                # 未知消息类型
                return msg.data, MessageType.NONE

        except TimeoutError:
            raise
        except Exception as e:
            self.metrics["errors"] += 1
            self.logger.error("Receive error: %s", e)
            raise

    def is_connected(self) -> bool:
        """检查连接是否处于活动状态

        Returns:
            bool: 已连接且 WebSocket 未关闭返回 True
        """
        return (
            self.state == WebSocketState.CONNECTED
            and self.websocket is not None
            and not self.websocket.closed
        )


class ReconnectionStrategy:
    """重连策略管理

    实现指数退避 + 随机抖动的重连策略。

    Attributes:
        config: WebSocket 配置对象
        attempt_count: 当前重连尝试次数
        last_attempt_time: 上次尝试时间戳
    """

    def __init__(self, config: WebSocketConfig):
        """初始化重连策略

        Args:
            config: WebSocket 配置对象
        """
        self.config = config
        self.attempt_count = 0
        self.last_attempt_time = 0.0

    def should_reconnect(self) -> bool:
        """检查是否应该继续重连

        Returns:
            bool: 未达到最大重连次数返回 True，``reconnect_attempts=0`` 表示无限重连
        """
        if self.config.reconnect_attempts == 0:
            # 配置文档一直声明 0 = 无限重连，而原实现是 `0 < 0` → 立即放弃，
            # 恰好把"永不停止"配成了"一次都不试"。
            return True
        return self.attempt_count < self.config.reconnect_attempts

    def get_delay(self) -> float:
        """计算下次重连的延迟时间

        使用指数退避算法：delay = min(base * 2^(n-1), max) + jitter

        Returns:
            float: 延迟时间（秒）
        """
        if self.attempt_count == 0:
            return 0.0

        # 指数退避
        delay = min(
            self.config.backoff_base * (2 ** (self.attempt_count - 1)),
            self.config.backoff_max,
        )

        # 随机抖动
        jitter = random.uniform(0, self.config.jitter_factor)
        return delay + jitter

    def on_attempt(self) -> None:
        """记录一次重连尝试"""
        self.attempt_count += 1
        self.last_attempt_time = time.time()

    def on_success(self) -> None:
        """重连成功，重置计数器"""
        self.attempt_count = 0

    def get_state(self) -> dict[str, Any]:
        """获取当前重连状态

        Returns:
            Dict[str, Any]: 包含尝试次数、上次尝试时间、最大次数的字典
        """
        return {
            "attempt_count": self.attempt_count,
            "last_attempt_time": self.last_attempt_time,
            "max_attempts": self.config.reconnect_attempts,
        }


class AsyncWebSocketClient:
    """异步 WebSocket 客户端 - 使用监听器模式

    高性能异步 WebSocket 客户端，支持多监听器、自动重连、
    消息广播和完善的指标统计。

    Attributes:
        config: WebSocket 配置对象
        logger: 日志记录器
        connection: 底层连接管理器
        reconnection: 重连策略管理器
        _listeners: 监听器字典
        _running: 运行状态标志
    """

    def __init__(
        self,
        uri: str,
        logger: logging.Logger | None = None,
        headers: dict[str, str] | None = None,
        heartbeat: float = 30.0,
        receive_timeout: float = 60.0,
        reconnect_attempts: int = 5,
        connect_timeout: float = 20.0,
        send_queue_size: int = 1024,
        session_timeout: float = 300.0,
        backoff_base: float = 1.0,
        backoff_max: float = 60.0,
        jitter_factor: float = 0.5,
        compression: int = 15,
        verify_ssl: bool = True,
        max_listeners: int = 1000,
        listener_buffer_size: int = 100,
    ):
        """初始化异步 WebSocket 客户端

        Args:
            uri: WebSocket 服务器地址
            logger: 可选的日志记录器，默认使用模块日志
            headers: 可选的连接请求头
            heartbeat: 心跳间隔（秒），默认 30.0
            receive_timeout: 接收超时（秒），默认 60.0
            reconnect_attempts: 最大重连次数，默认 5
            connect_timeout: 连接超时（秒），默认 20.0
            send_queue_size: 发送队列大小，默认 1024
            session_timeout: 会话超时（秒），默认 300.0
            backoff_base: 退避基数（秒），默认 1.0
            backoff_max: 最大退避（秒），默认 60.0
            jitter_factor: 抖动因子，默认 0.5
            compression: 压缩级别，默认 15
            verify_ssl: 验证 SSL，默认 True
            max_listeners: 最大监听器数，默认 1000
            listener_buffer_size: 监听器缓冲区大小，默认 100
        """
        # 创建配置
        self.config = WebSocketConfig(
            uri=uri,
            headers=headers or {},
            heartbeat=heartbeat,
            receive_timeout=receive_timeout,
            reconnect_attempts=reconnect_attempts,
            connect_timeout=connect_timeout,
            send_queue_size=send_queue_size,
            session_timeout=session_timeout,
            backoff_base=backoff_base,
            backoff_max=backoff_max,
            jitter_factor=jitter_factor,
            compression=compression,
            verify_ssl=verify_ssl,
            max_listeners=max_listeners,
            listener_buffer_size=listener_buffer_size,
        )

        # 设置日志
        self.logger = logger or logging.getLogger(__name__)

        # 核心组件
        self.connection = AioHttpWebSocketConnection(self.config, self.logger)
        self.reconnection = ReconnectionStrategy(self.config)

        # 监听器管理
        self._listeners: dict[ListenerId, WebSocketListener] = {}
        self._listeners_lock = threading.Lock()

        # 状态控制
        self._running = False
        self._main_task: asyncio.Task | None = None
        self._lifecycle_lock = asyncio.Lock()
        self._shutdown_lock = asyncio.Lock()
        self._ready = False
        self._ever_ready = False
        self._ready_event = asyncio.Event()
        self._startup_error: ConnectionError | None = None
        self._health_state = ConnectionHealthState.STOPPED
        self._last_success_at: float | None = None
        self._last_error_at: float | None = None
        self._last_error: BaseException | None = None
        self._health_handler: Callable[[ConnectionHealth], None] | None = None

        # 发送队列
        self._send_queue: asyncio.Queue[_SendMessage] = asyncio.Queue(
            maxsize=self.config.send_queue_size
        )
        # 消息离开有界队列后、底层 send 确认前由客户端继续持有。断线或 sibling
        # task 取消时不能 await 回填满队列，否则重连和关闭都会被反向阻塞。
        self._inflight_message: _SendMessage | object = _NO_INFLIGHT_MESSAGE
        self._send_retries = 0
        self._send_dropped = 0

    @property
    def running(self) -> bool:
        """检查客户端是否正在运行

        Returns:
            bool: 正在运行返回 True
        """
        return self._running

    @property
    def ready(self) -> bool:
        """首次连接已成功且当前底层连接仍可用."""
        return self._ready and self.connection.is_connected()

    @property
    def health(self) -> ConnectionHealth:
        """返回当前连接健康快照."""
        error = self._last_error
        return ConnectionHealth(
            state=self._health_state,
            last_success_at=self._last_success_at,
            last_error_at=self._last_error_at,
            last_error_type=type(error).__name__ if error is not None else None,
            last_error_message=str(error) if error is not None else None,
        )

    def set_health_handler(
        self,
        handler: Callable[[ConnectionHealth], None] | None,
    ) -> None:
        """设置连接健康变化的同步回调."""
        self._health_handler = handler

    async def __aenter__(self):
        """异步上下文管理器入口

        Returns:
            AsyncWebSocketClient: 客户端实例
        """
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪
        """
        await self.stop()

    async def start(
        self,
        *,
        wait_ready: bool = False,
        ready_timeout: float | None = None,
    ) -> None:
        """启动客户端

        ``wait_ready=False`` 只保证主任务已创建；``True`` 则等待
        首次 WebSocket 连接成功。有限重连用尽或就绪超时会同步
        抛出 :class:`ConnectionError`，且本次新启动的客户端会完整停止。
        """
        started_here = False
        async with self._lifecycle_lock:
            if not self._running:
                self.reconnection.on_success()
                self._ready = False
                self._ever_ready = False
                self._ready_event.clear()
                self._startup_error = None
                self._running = True
                self._set_health(ConnectionHealthState.STARTING)
                self._main_task = asyncio.create_task(self._main_loop())
                started_here = True
                self.logger.info("WebSocket client started")

        if not wait_ready:
            return
        try:
            await self.wait_until_ready(timeout=ready_timeout)
        except BaseException:
            if started_here:
                await self.stop()
            raise

    async def wait_until_ready(self, timeout: float | None = None) -> None:
        """等待首次连接就绪，或传播最终首连失败."""
        if self._ever_ready:
            return
        try:
            if timeout is None:
                await self._ready_event.wait()
            else:
                await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
        except TimeoutError as exc:
            error = ConnectionError("WebSocket ready timeout after %ss" % timeout)
            self._record_error(error)
            raise error from exc

        if self._ever_ready:
            return
        if self._startup_error is not None:
            raise self._startup_error
        raise ConnectionError("WebSocket stopped before first connection became ready")

    async def stop(self) -> None:
        """停止客户端（外部入口）

        优雅地取消主任务，然后清理监听器与连接。幂等。

        主任务自身**不得**走这条路径：``await self._main_task`` 在主任务里执行
        会抛 ``RuntimeError``（Task 不能 await 自己），而此时 ``_running``
        已被置 False，异常传出后 finally 里的再次 stop() 会被开头的早退挡掉，
        于是监听器与 aiohttp session 全部泄漏。内部收尾请用 :meth:`_shutdown`。
        """
        async with self._lifecycle_lock:
            self._running = False
            self._ready = False
            self._set_health(ConnectionHealthState.STOPPING)
            main_task = self._main_task
            self._main_task = None

            if not self._ready_event.is_set():
                self._startup_error = ConnectionError(
                    "WebSocket stopped before first connection became ready"
                )
                self._ready_event.set()

            if main_task is not None and main_task is not asyncio.current_task():
                self.logger.debug("WebSocket client stopping")
                main_task.cancel()
                try:
                    await main_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.logger.error("Main task ended with error: %s", e)

            await self._shutdown()

    async def _shutdown(self) -> None:
        """清理监听器与底层连接（幂等，不触碰主任务）

        供 :meth:`stop` 和 :meth:`_main_loop` 的 finally 共用：
        无论从外部停止还是主循环自己退出，资源释放都走同一条路径。
        """
        async with self._shutdown_lock:
            self._running = False
            self._ready = False

            if not self._ready_event.is_set():
                self._startup_error = ConnectionError(
                    "WebSocket stopped before first connection became ready"
                )
                self._ready_event.set()

            # 关闭所有监听器
            with self._listeners_lock:
                listeners = list(self._listeners.values())
                self._listeners.clear()
            for listener in listeners:
                listener.close()

            # stop 是终止当前客户端生命周期，不把旧消息带到下一次 start。连接切换
            # 过程不会进入 shutdown，因此普通重连仍会优先重放 in-flight 消息。
            self._send_dropped += self._clear_send_buffer()

            # 关闭连接
            await self.connection.close()
            self._set_health(ConnectionHealthState.STOPPED)

            self.logger.info("WebSocket client stopped")

    async def create_listener(self, buffer_size: int | None = None) -> ListenerId:
        """创建消息监听器

        如果监听器数量达到上限，自动淘汰最旧的监听器。

        Args:
            buffer_size: 缓冲区大小，默认使用配置值

        Returns:
            ListenerId: 新监听器的唯一标识符
        """
        if buffer_size is None:
            buffer_size = self.config.listener_buffer_size

        listener = WebSocketListener(buffer_size)
        evicted: WebSocketListener | None = None

        with self._listeners_lock:
            # 检查监听器数量限制。淘汰只在锁内做 dict 操作，
            # 关闭动作留到临界区之外——在持有非重入锁时调用会重入同一把锁的
            # remove_listener，是一条确定的死锁路径。
            if len(self._listeners) >= self.config.max_listeners:
                evicted = self._pop_oldest_listener_locked()

            self._listeners[listener.id] = listener

        if evicted is not None:
            evicted.close()
            self.logger.warning(
                "Evicted oldest listener due to max listeners: %s", evicted.id
            )

        self.logger.debug("Listener created: %s", listener.id)
        return listener.id

    async def remove_listener(self, listener_id: ListenerId) -> None:
        """移除指定监听器

        Args:
            listener_id: 要移除的监听器 ID
        """
        with self._listeners_lock:
            listener = self._listeners.pop(listener_id, None)

        if listener:
            listener.close()
            self.logger.debug("Listener removed: %s", listener_id)

    async def get_message(
        self, listener_id: ListenerId, timeout: float | None = None
    ) -> tuple[Any, MessageType]:
        """从指定监听器获取消息（阻塞）

        Args:
            listener_id: 监听器 ID
            timeout: 超时时间（秒），None 表示无限等待

        Returns:
            Tuple[Any, MessageType]: 消息内容和类型

        Raises:
            ListenerEvictedError: 监听器不存在时抛出
            ListenerClosedError: 监听器已关闭时抛出
            asyncio.TimeoutError: 超时时抛出
        """
        with self._listeners_lock:
            listener = self._listeners.get(listener_id)

        if not listener:
            raise ListenerEvictedError("Listener %s not found" % listener_id)

        return await listener.get(timeout)

    def get_message_nowait(
        self, listener_id: ListenerId
    ) -> tuple[Any, MessageType] | None:
        """从指定监听器非阻塞获取消息

        Args:
            listener_id: 监听器 ID

        Returns:
            Optional[Tuple[Any, MessageType]]: 消息内容和类型，无数据返回 None

        Raises:
            ListenerEvictedError: 监听器不存在时抛出
            ListenerClosedError: 监听器已关闭时抛出
        """
        with self._listeners_lock:
            listener = self._listeners.get(listener_id)

        if not listener:
            raise ListenerEvictedError("Listener %s not found" % listener_id)

        return listener.get_nowait()

    async def send(self, message: _SendMessage) -> None:
        """发送消息到 WebSocket 服务器

        消息会被放入发送队列，由后台任务异步发送。
        断线时正在发送的单条消息会在重连后优先重放，因此传输语义是
        at-least-once；显式 :meth:`stop` 会丢弃尚未确认发送的消息。

        Args:
            message: 要发送的消息，支持字符串、字节或字典

        Raises:
            ConnectionError: 客户端未运行时抛出
            WebSocketError: 发送队列满时抛出
        """
        if not self._running:
            raise ConnectionError("Client not running")

        try:
            self._send_queue.put_nowait(message)
        except QueueFull:
            raise WebSocketError("Send queue is full")

    def _pop_oldest_listener_locked(self) -> WebSocketListener | None:
        """摘除创建时间最早的监听器并返回它（**调用方必须已持有锁**）

        只做字典操作、不做任何 ``await``，也不调用 ``close()``——
        关闭动作由调用方在释放锁之后执行。

        Returns:
            被摘除的监听器，没有监听器时返回 None
        """
        if not self._listeners:
            return None

        oldest_id = min(
            self._listeners, key=lambda lid: self._listeners[lid].created_at
        )
        return self._listeners.pop(oldest_id, None)

    async def _broadcast_message(self, message: Any, msg_type: MessageType) -> None:
        """广播消息到所有监听器

        如果某个监听器队列满，该监听器会被自动移除。

        Args:
            message: 消息内容
            msg_type: 消息类型
        """
        listeners_to_remove = []

        with self._listeners_lock:
            listeners = list(self._listeners.values())

        for listener in listeners:
            if not await listener.put(message, msg_type):
                # 监听器队列满，标记为移除
                listeners_to_remove.append(listener.id)

        # 移除无法处理消息的监听器
        for listener_id in listeners_to_remove:
            await self.remove_listener(listener_id)
            self.logger.warning("Listener evicted due to buffer full: %s", listener_id)

    def get_metrics(self) -> dict[str, Any]:
        """获取客户端运行指标

        Returns:
            Dict[str, Any]: 包含连接指标、重连状态、监听器统计的字典
        """
        connection_metrics = self.connection.metrics.copy()
        reconnection_state = self.reconnection.get_state()

        with self._listeners_lock:
            active_listeners = len(self._listeners)

        return {
            "connection": connection_metrics,
            "reconnection": reconnection_state,
            "listeners": {
                "active": active_listeners,
                "max": self.config.max_listeners,
            },
            "running": self._running,
            "ready": self.ready,
            "health": self.health.state.value,
            "send_queue": {
                "pending": self._send_queue.qsize(),
                "capacity": self.config.send_queue_size,
                "inflight": self._inflight_message is not _NO_INFLIGHT_MESSAGE,
                "retried": self._send_retries,
                "dropped": self._send_dropped,
            },
        }

    async def _main_loop(self) -> None:
        """主事件循环

        管理连接生命周期，协调发送和接收任务。
        处理连接断开、重连和异常恢复。

        **首次连接也在循环内**，与重连走同一条 :meth:`_handle_disconnected`
        路径（首次的退避为 0，立即尝试）。原实现把首连放在 while 之前，
        首连失败会直接落进 finally —— 重连策略对"服务端还没起来"这种最常见的
        场景完全不生效。
        """
        self.logger.debug("Main loop started")

        try:
            while self._running:
                # 处理连接状态（含首次连接）
                if not self.connection.is_connected():
                    await self._handle_disconnected()
                    continue

                # 并行处理发送和接收
                send_task = asyncio.create_task(self._process_send_queue())
                recv_task = asyncio.create_task(self._process_receive())

                done, pending = await asyncio.wait(
                    [send_task, recv_task], return_when=asyncio.FIRST_COMPLETED
                )

                # 取消未完成的任务，并等它们真正结束（否则退出时会出现
                # "Task was destroyed but it is pending!" 告警）
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

                # 处理异常
                for task in done:
                    if task.cancelled():
                        continue
                    exc = task.exception()
                    if exc is not None:
                        self.logger.error("Task error: %s", exc)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error("Main loop error: %s", e)
        finally:
            # 只做资源清理，不要 await 主任务自己
            await self._shutdown()
            self.logger.debug("Main loop ended")

    async def _handle_disconnected(self) -> None:
        """处理连接（首次或断线重连）

        根据重连策略决定是否继续尝试，并执行指数退避等待。
        超过最大次数时只置 ``_running=False``，让 :meth:`_main_loop` 自然退出、
        由它的 finally 统一清理——不能在这里 ``await self.stop()``，
        那等于在主任务内部 await 主任务自己。
        """
        if not self.reconnection.should_reconnect():
            self.logger.error("Max reconnection attempts reached")
            error = self._last_error
            if not isinstance(error, ConnectionError):
                error = ConnectionError("Max reconnection attempts reached")
                self._record_error(error)
            if not self._ever_ready:
                self._startup_error = error
                self._ready_event.set()
            self._running = False
            return

        if self._ever_ready and self._ready:
            self._ready = False
            self._set_health(ConnectionHealthState.DEGRADED)

        delay = self.reconnection.get_delay()
        if delay > 0:
            self.logger.info("Reconnection delay: %.2fs", delay)
            await asyncio.sleep(delay)

        self.reconnection.on_attempt()
        self.logger.info("Connection attempt: %s", self.reconnection.attempt_count)

        try:
            await self.connection.connect()
            self.reconnection.on_success()
            self._ready = True
            self._ever_ready = True
            self._last_success_at = time.time()
            self._set_health(ConnectionHealthState.READY)
            self._ready_event.set()
        except ConnectionError as e:
            self._record_error(e)
            if self._ever_ready:
                self._set_health(ConnectionHealthState.DEGRADED, error=e)
            self.logger.error("Connection failed: %s", e)

    def _record_error(self, error: BaseException) -> None:
        """记录最近一次连接错误."""
        self._last_error = error
        self._last_error_at = time.time()

    def _set_health(
        self,
        state: ConnectionHealthState,
        *,
        error: BaseException | None = None,
    ) -> None:
        """更新并通知连接健康状态，观察者异常不影响 I/O 循环."""
        if error is not None:
            self._record_error(error)
        self._health_state = state
        handler = self._health_handler
        if handler is None:
            return
        try:
            handler(self.health)
        except Exception:
            self.logger.exception("WebSocket health handler failed")

    async def _process_send_queue(self) -> None:
        """处理发送队列

        持续从队列取出消息并发送。消息离开队列后先进入单一 retry slot；连接
        中断或 task 取消只保留该 slot，不执行任何可能等待队列容量的操作。重连后
        优先重放 slot，再读取普通队列。
        """
        while self._running:
            if not self.connection.is_connected():
                # 直接返回，交还控制权给 _main_loop 去走重连。
                # 原来这里 sleep(0.1) 后 continue：两个子任务都永不结束，
                # _main_loop 一直卡在 asyncio.wait 上，断线后既 100% CPU 忙等
                # 又永远不会重连。
                return
            from_queue = False
            if self._inflight_message is _NO_INFLIGHT_MESSAGE:
                try:
                    message = await asyncio.wait_for(
                        self._send_queue.get(), timeout=0.1
                    )
                except TimeoutError:
                    continue
                self._inflight_message = message
                from_queue = True
            else:
                message = cast(_SendMessage, self._inflight_message)
                self._send_retries += 1

            try:
                await self.connection.send(message)
            except asyncio.CancelledError:
                # slot 继续持有消息。这里不能 await queue.put()：队列可能已经被
                # 并发生产者填满，导致一次 cancel 无法结束发送任务。
                raise
            except ConnectionError:
                # 保留 slot 并退出，主循环完成重连后会优先重放。
                break
            except Exception as e:
                self.logger.error("Send processing error: %s", e)
                self._inflight_message = _NO_INFLIGHT_MESSAGE
                self._send_dropped += 1
            else:
                self._inflight_message = _NO_INFLIGHT_MESSAGE
            finally:
                if from_queue:
                    self._send_queue.task_done()

    def _clear_send_buffer(self) -> int:
        """丢弃当前生命周期尚未确认的消息并返回数量."""
        dropped = int(self._inflight_message is not _NO_INFLIGHT_MESSAGE)
        self._inflight_message = _NO_INFLIGHT_MESSAGE
        while True:
            try:
                self._send_queue.get_nowait()
            except QueueEmpty:
                break
            else:
                self._send_queue.task_done()
                dropped += 1
        return dropped

    async def _process_receive(self) -> None:
        """处理接收消息

        持续接收消息并广播到所有监听器，处理超时和连接错误。
        """
        while self._running:
            if not self.connection.is_connected():
                # 同 _process_send_queue：返回主循环触发重连，而不是原地忙等
                return
            try:
                message, msg_type = await self.connection.receive()

                # 广播消息到所有监听器
                await self._broadcast_message(message, msg_type)

                if msg_type == MessageType.Close:
                    # 服务端主动关闭：连接已经不可用，必须回到主循环走重连。
                    # 原实现只是广播完继续 while，而 is_connected() 已为 False，
                    # 于是掉进上面那个 0.1s 忙等分支，永不重连。
                    self.logger.warning("Received CLOSE frame from server")
                    await self.connection.close()
                    return

            except TimeoutError:
                # 只是没有消息，继续等待
                continue
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error("Receive processing error: %s", e)
                # 接收错误通常意味着连接问题，关闭连接触发重连
                try:
                    await self.connection.close()
                except Exception:
                    pass
                break
