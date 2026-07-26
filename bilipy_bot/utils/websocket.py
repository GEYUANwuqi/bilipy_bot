# @Author Fish.zh@outlook.com
# @Version 1.1
import asyncio
import json
import logging
import random
import threading
import time
import uuid
from asyncio import QueueFull
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NewType

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
        if self.reconnect_attempts < 0:
            raise ValueError("Reconnect attempts cannot be negative")


_CLOSE_SENTINEL = object()
"""放入监听器队列的关闭哨兵.

``close()`` 需要唤醒已经阻塞在 ``queue.get()`` 上的消费者——只置标志位的话，
等待者会永远挂在那里等一条永不到来的消息。哨兵被 ``get()`` 识别后转换为
``ListenerClosedError``，因此不会被误当成业务消息。
"""


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

        # 发送队列
        self._send_queue = asyncio.Queue(maxsize=self.config.send_queue_size)

    @property
    def running(self) -> bool:
        """检查客户端是否正在运行

        Returns:
            bool: 正在运行返回 True
        """
        return self._running

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

    async def start(self) -> None:
        """启动客户端

        启动主事件循环，开始处理连接、发送和接收。
        如果已经在运行，直接返回。
        """
        if self._running:
            return

        self._running = True
        self._main_task = asyncio.create_task(self._main_loop())
        self.logger.info("WebSocket client started")

    async def stop(self) -> None:
        """停止客户端（外部入口）

        优雅地取消主任务，然后清理监听器与连接。幂等。

        主任务自身**不得**走这条路径：``await self._main_task`` 在主任务里执行
        会抛 ``RuntimeError``（Task 不能 await 自己），而此时 ``_running``
        已被置 False，异常传出后 finally 里的再次 stop() 会被开头的早退挡掉，
        于是监听器与 aiohttp session 全部泄漏。内部收尾请用 :meth:`_shutdown`。
        """
        self._running = False
        main_task = self._main_task
        self._main_task = None

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
        self._running = False

        # 关闭所有监听器
        with self._listeners_lock:
            listeners = list(self._listeners.values())
            self._listeners.clear()
        for listener in listeners:
            listener.close()

        # 关闭连接
        await self.connection.close()

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

    async def send(self, message: str | bytes | dict) -> None:
        """发送消息到 WebSocket 服务器

        消息会被放入发送队列，由后台任务异步发送。

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
            self._running = False
            return

        delay = self.reconnection.get_delay()
        if delay > 0:
            self.logger.info("Reconnection delay: %.2fs", delay)
            await asyncio.sleep(delay)

        self.reconnection.on_attempt()
        self.logger.info("Connection attempt: %s", self.reconnection.attempt_count)

        try:
            await self.connection.connect()
            self.reconnection.on_success()
        except ConnectionError as e:
            self.logger.error("Connection failed: %s", e)

    async def _process_send_queue(self) -> None:
        """处理发送队列

        持续从队列取出消息并发送，处理连接中断时的消息回退。
        """
        while self._running:
            if not self.connection.is_connected():
                # 直接返回，交还控制权给 _main_loop 去走重连。
                # 原来这里 sleep(0.1) 后 continue：两个子任务都永不结束，
                # _main_loop 一直卡在 asyncio.wait 上，断线后既 100% CPU 忙等
                # 又永远不会重连。
                return
            try:
                message = await asyncio.wait_for(self._send_queue.get(), timeout=0.1)
            except TimeoutError:
                continue

            try:
                await self.connection.send(message)
            except asyncio.CancelledError:
                # 将消息放回队列并重新抛出
                await self._send_queue.put(message)
                raise
            except ConnectionError:
                # 连接不可用，将消息重新入队并退出，触发重连
                await self._send_queue.put(message)
                break
            except Exception as e:
                self.logger.error("Send processing error: %s", e)
            finally:
                try:
                    self._send_queue.task_done()
                except Exception:
                    pass

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


class SyncWebSocketClient:
    """同步 WebSocket 客户端包装器

    为同步代码提供 WebSocket 客户端功能，内部在后台线程运行异步事件循环。
    所有方法都是线程安全的。

    Attributes:
        _client: 底层异步客户端实例
        _loop: 事件循环
        _thread: 后台线程
        _running: 运行状态
    """

    def __init__(self, *args, **kwargs):
        """初始化同步客户端

        Args:
            *args: 传递给 AsyncWebSocketClient 的位置参数
            **kwargs: 传递给 AsyncWebSocketClient 的关键字参数
        """
        self._client = AsyncWebSocketClient(*args, **kwargs)
        self._loop = asyncio.new_event_loop()
        self._thread = None
        self._running = False

    def start(self) -> None:
        """启动客户端（在后台线程中运行事件循环）

        如果已经在运行，直接返回。启动后会等待客户端真正就绪。
        """
        if self._running:
            return

        self._running = True

        def run_loop():
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._client.start())
                self._loop.run_forever()
            finally:
                self._loop.close()

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

        # 等待客户端真正启动
        for i in range(10):
            if self._client._running:
                break
            time.sleep(0.1)

    def stop(self) -> None:
        """停止客户端

        优雅地停止事件循环和后台线程，清理资源。
        如果已经停止，直接返回。
        """
        if not self._running:
            return

        self._running = False

        # 在事件循环线程中停止客户端
        future = asyncio.run_coroutine_threadsafe(self._client.stop(), self._loop)
        future.result(timeout=10)  # 等待停止完成

        # 停止事件循环
        self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread:
            self._thread.join(timeout=5)

    def create_listener(self, buffer_size: int | None = None) -> str:
        """创建消息监听器（同步）

        Args:
            buffer_size: 缓冲区大小，默认使用配置值

        Returns:
            str: 监听器 ID 字符串
        """
        future = asyncio.run_coroutine_threadsafe(
            self._client.create_listener(buffer_size), self._loop
        )
        return future.result(timeout=10)

    def remove_listener(self, listener_id: ListenerId) -> None:
        """移除监听器（同步）

        Args:
            listener_id: 要移除的监听器 ID
        """
        future = asyncio.run_coroutine_threadsafe(
            self._client.remove_listener(listener_id), self._loop
        )
        future.result(timeout=10)

    def get_message(
        self, listener_id: ListenerId, timeout: float | None = None
    ) -> tuple[Any, MessageType]:
        """获取消息（同步阻塞）

        Args:
            listener_id: 监听器 ID
            timeout: 超时时间（秒），包含线程调度时间

        Returns:
            Tuple[Any, MessageType]: 消息内容和类型
        """
        future = asyncio.run_coroutine_threadsafe(
            self._client.get_message(listener_id, timeout), self._loop
        )
        return future.result(timeout=timeout)

    def get_message_nowait(
        self, listener_id: ListenerId
    ) -> tuple[Any, MessageType] | None:
        """非阻塞获取消息（同步）

        Args:
            listener_id: 监听器 ID

        Returns:
            Optional[Tuple[Any, MessageType]]: 消息内容和类型，无数据返回 None
        """
        return self._client.get_message_nowait(listener_id)

    def send(self, message: str | bytes | dict) -> None:
        """发送消息（同步）

        Args:
            message: 要发送的消息，支持字符串、字节或字典
        """
        future = asyncio.run_coroutine_threadsafe(
            self._client.send(message), self._loop
        )
        future.result(timeout=10)

    def get_metrics(self) -> dict[str, Any]:
        """获取客户端指标（同步）

        Returns:
            Dict[str, Any]: 客户端运行指标字典
        """
        return self._client.get_metrics()

    def __enter__(self):
        """上下文管理器入口

        Returns:
            SyncWebSocketClient: 客户端实例
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪
        """
        self.stop()
