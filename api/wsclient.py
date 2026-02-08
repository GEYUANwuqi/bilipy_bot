import asyncio
import json
import logging
import random
import threading
import time
import uuid
from asyncio import QueueFull
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union

import aiohttp
from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType

from .abc import (
    ABCWebSocketClient,
    ListenerClosedError,
    ListenerEvictedError,
    ListenerId,
    MessageType,
    WebSocketError,
    WebSocketState,
)


@dataclass
class WebSocketConfig:
    """WebSocket 配置"""

    uri: str
    headers: Dict[str, str] = field(default_factory=dict)
    heartbeat: float = 30.0
    receive_timeout: float = 60.0
    reconnect_attempts: int = None
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
        """配置验证"""
        if not self.uri.startswith(("ws://", "wss://")):
            raise ValueError("URI must start with ws:// or wss://")
        if self.heartbeat <= 0:
            raise ValueError("Heartbeat must be positive")
        if self.reconnect_attempts < 0:
            raise ValueError("Reconnect attempts cannot be negative")


class WebSocketListener:
    """WebSocket 监听器"""

    def __init__(self, buffer_size: int = 100):
        self.id = str(uuid.uuid4())
        self.queue = asyncio.Queue(maxsize=buffer_size)
        self.created_at = time.time()
        self._closed = False

    async def put(self, message: Any, msg_type: MessageType):
        """放入消息"""
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

    async def get(self, timeout: Optional[float] = None) -> Tuple[Any, MessageType]:
        """获取消息"""
        if self._closed:
            raise ListenerClosedError(f"Listener {self.id} is closed")

        try:
            if timeout is None:
                return await self.queue.get()
            else:
                return await asyncio.wait_for(self.queue.get(), timeout=timeout)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if self._closed:
                raise ListenerClosedError(f"Listener {self.id} is closed") from e
            raise

    def get_nowait(self) -> Optional[Tuple[Any, MessageType]]:
        """非阻塞获取消息"""
        if self._closed:
            raise ListenerClosedError(f"Listener {self.id} is closed")

        try:
            return self.queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def close(self):
        """关闭监听器"""
        self._closed = True
        # 清空队列以释放等待的消费者
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    @property
    def is_closed(self) -> bool:
        return self._closed

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await self.get()
        except ListenerClosedError:
            raise StopAsyncIteration


class AioHttpWebSocketConnection:
    """基于 aiohttp 的 WebSocket 连接"""

    def __init__(self, config: WebSocketConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

        self.websocket: Optional[ClientWebSocketResponse] = None
        self.session: Optional[ClientSession] = None
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

    async def connect(self):
        """建立连接"""
        if self.state in [WebSocketState.Connecting, WebSocketState.CONNECTED]:
            return

        self.state = WebSocketState.Connecting
        self.metrics["connection_attempts"] += 1
        self.logger.info(f"Connecting to {self.config.uri}")

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
            self.logger.info(f"Connected to {self.config.uri}")

        except Exception as e:
            self.state = WebSocketState.Disconnected
            self.metrics["failed_connections"] += 1

            # 清理资源
            if self.session:
                await self.session.close()
                self.session = None

            self.logger.error(f"Connection failed: {self.config.uri}, error: {e}")
            if "wbits=" in str(e):
                self.logger.error("Detected zlib wbits compression error")
                if 15 < self.config.compression < 9:
                    self.logger.info("Enabled compression reconnection")
                    self.config.compression = 15
                else:
                    self.logger.info("Disable compression reconnection")
                    self.config.compression = 0

            raise ConnectionError(f"Connection failed: {e}")

    async def close(self):
        """关闭连接"""
        if self.state == WebSocketState.Closed:
            return

        self.state = WebSocketState.Closing
        self.logger.debug("Closing connection")

        try:
            if self.websocket:
                await self.websocket.close()
        except Exception as e:
            self.logger.error(f"WebSocket close error: {e}")

        try:
            if self.session:
                await self.session.close()
        except Exception as e:
            self.logger.error(f"Session close error: {e}")
        finally:
            self.websocket = None
            self.session = None
            self.state = WebSocketState.Closed
            self.logger.info("Connection closed")

    async def send(self, message: Union[str, bytes, Dict]):
        """发送消息"""
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
            self.logger.error(f"Send error: {e}")
            raise

    async def receive(self) -> Tuple[Any, MessageType]:
        """接收消息"""
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
                self.logger.error(f"WebSocket error: {msg.data}")
                return msg.data, MessageType.Error

            else:
                # 未知消息类型
                return msg.data, MessageType.NONE

        except asyncio.TimeoutError:
            raise
        except Exception as e:
            self.metrics["errors"] += 1
            self.logger.error(f"Receive error: {e}")
            raise

    def is_connected(self) -> bool:
        """检查连接状态"""
        return (
            self.state == WebSocketState.CONNECTED
            and self.websocket is not None
            and not self.websocket.closed
        )


class ReconnectionStrategy:
    """重连策略"""

    def __init__(self, config: WebSocketConfig):
        self.config = config
        self.attempt_count = 0
        self.last_attempt_time = 0.0

    def should_reconnect(self) -> bool:
        """是否应该重连"""
        return self.attempt_count < self.config.reconnect_attempts

    def get_delay(self) -> float:
        """获取重连延迟"""
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

    def on_attempt(self):
        """记录重连尝试"""
        self.attempt_count += 1
        self.last_attempt_time = time.time()

    def on_success(self):
        """重置重连状态"""
        self.attempt_count = 0

    def get_state(self) -> Dict[str, Any]:
        """获取重连状态"""
        return {
            "attempt_count": self.attempt_count,
            "last_attempt_time": self.last_attempt_time,
            "max_attempts": self.config.reconnect_attempts,
        }


class AsyncWebSocketClient(ABCWebSocketClient):
    """异步 WebSocket 客户端 - 使用监听器模式"""

    def __init__(
        self,
        uri: str,
        logger: Optional[logging.Logger] = None,
        headers: Optional[Dict[str, str]] = None,
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
        self._listeners: Dict[ListenerId, WebSocketListener] = {}
        self._listeners_lock = threading.Lock()

        # 状态控制
        self._running = False
        self._main_task: Optional[asyncio.Task] = None

        # 发送队列
        self._send_queue = asyncio.Queue(maxsize=self.config.send_queue_size)

    @property
    def running(self) -> bool:
        return self._running

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.stop()

    async def start(self):
        """启动客户端"""
        if self._running:
            return

        self._running = True
        self._main_task = asyncio.create_task(self._main_loop())
        self.logger.info("WebSocket client started")

    async def stop(self):
        """停止客户端"""
        if not self._running:
            return

        self._running = False
        self.logger.debug("WebSocket client stopping")

        # 取消主任务
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass

        # 关闭所有监听器
        with self._listeners_lock:
            for listener in self._listeners.values():
                listener.close()
            self._listeners.clear()

        # 关闭连接
        await self.connection.close()

        self.logger.info("WebSocket client stopped")

    async def create_listener(self, buffer_size: Optional[int] = None) -> ListenerId:
        """创建监听器"""
        if buffer_size is None:
            buffer_size = self.config.listener_buffer_size

        listener = WebSocketListener(buffer_size)

        with self._listeners_lock:
            # 检查监听器数量限制
            if len(self._listeners) >= self.config.max_listeners:
                await self._evict_oldest_listener()

            self._listeners[listener.id] = listener

        self.logger.debug(f"Listener created: {listener.id}")
        return listener.id

    async def remove_listener(self, listener_id: ListenerId):
        """移除监听器"""
        with self._listeners_lock:
            listener = self._listeners.pop(listener_id, None)

        if listener:
            listener.close()
            self.logger.debug(f"Listener removed: {listener_id}")

    async def get_message(
        self, listener_id: ListenerId, timeout: Optional[float] = None
    ) -> Tuple[Any, MessageType]:
        """从监听器获取消息（异步阻塞）"""
        with self._listeners_lock:
            listener = self._listeners.get(listener_id)

        if not listener:
            raise ListenerEvictedError(f"Listener {listener_id} not found")

        return await listener.get(timeout)

    def get_message_nowait(self, listener_id: str) -> Optional[Tuple[Any, MessageType]]:
        """非阻塞获取消息"""
        with self._listeners_lock:
            listener = self._listeners.get(listener_id)

        if not listener:
            raise ListenerEvictedError(f"Listener {listener_id} not found")

        return listener.get_nowait()

    async def send(self, message: Union[str, bytes, Dict]):
        """发送消息"""
        if not self._running:
            raise ConnectionError("Client not running")

        try:
            self._send_queue.put_nowait(message)
        except QueueFull:
            raise WebSocketError("Send queue is full")

    async def _evict_oldest_listener(self):
        """淘汰最旧的监听器"""
        if not self._listeners:
            return

        # 找到最旧的监听器
        oldest_id = None
        oldest_time = float("inf")

        for listener_id, listener in self._listeners.items():
            if listener.created_at < oldest_time:
                oldest_time = listener.created_at
                oldest_id = listener_id

        if oldest_id:
            await self.remove_listener(oldest_id)
            self.logger.warning(
                f"Evicted oldest listener due to max listeners: {oldest_id}"
            )

    async def _broadcast_message(self, message: Any, msg_type: MessageType):
        """广播消息到所有监听器"""
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
            self.logger.warning(f"Listener evicted due to buffer full: {listener_id}")

    def get_metrics(self) -> Dict[str, Any]:
        """获取客户端指标"""
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

    async def _main_loop(self):
        """主事件循环"""
        self.logger.debug("Main loop started")

        try:
            await self.connection.connect()
            while self._running:
                # 处理连接状态
                if not self.connection.is_connected():
                    await self._handle_disconnected()
                    continue

                # 并行处理发送和接收
                send_task = asyncio.create_task(self._process_send_queue())
                recv_task = asyncio.create_task(self._process_receive())

                done, pending = await asyncio.wait(
                    [send_task, recv_task], return_when=asyncio.FIRST_COMPLETED
                )

                # 取消未完成的任务
                for task in pending:
                    task.cancel()

                # 处理异常
                for task in done:
                    if task.exception():
                        self.logger.error(f"Task error: {task.exception()}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Main loop error: {e}")
        finally:
            await self.stop()
            self.logger.debug("Main loop ended")

    async def _handle_disconnected(self):
        """处理断开连接状态"""
        if self.reconnection.should_reconnect():
            delay = self.reconnection.get_delay()
            if delay > 0:
                self.logger.info(f"Reconnection delay: {delay:.2f}s")
                await asyncio.sleep(delay)

            self.reconnection.on_attempt()
            self.logger.info(f"Reconnection attempt: {self.reconnection.attempt_count}")

            try:
                await self.connection.connect()
                self.reconnection.on_success()
            except ConnectionError as e:
                self.logger.error(f"Reconnection failed: {e}")
        else:
            self.logger.error("Max reconnection attempts reached")
            await self.stop()

    async def _process_send_queue(self):
        """处理发送队列"""
        while self._running:
            if not self.connection.is_connected():
                await asyncio.sleep(0.1)
                continue
            try:
                message = await asyncio.wait_for(self._send_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
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
                self.logger.error(f"Send processing error: {e}")
            finally:
                try:
                    self._send_queue.task_done()
                except Exception:
                    pass

    async def _process_receive(self):
        """处理接收消息"""
        while self._running:
            if not self.connection.is_connected():
                await asyncio.sleep(0.1)
                continue
            try:
                message, msg_type = await self.connection.receive()

                # 广播消息到所有监听器
                await self._broadcast_message(message, msg_type)

            except asyncio.TimeoutError:
                # 只是没有消息，继续等待
                continue
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error(f"Receive processing error: {e}")
                # 接收错误通常意味着连接问题，关闭连接触发重连
                try:
                    await self.connection.close()
                except Exception:
                    pass
                break


class SyncWebSocketClient(ABCWebSocketClient):
    """同步 WebSocket 客户端包装器 - 用于跨线程使用"""

    def __init__(self, *args, **kwargs):
        self._client = AsyncWebSocketClient(*args, **kwargs)
        self._loop = asyncio.new_event_loop()
        self._thread = None
        self._running = False

    def start(self):
        """启动客户端（在后台线程中运行事件循环）"""
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

    def stop(self):
        """停止客户端"""
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

    def create_listener(self, buffer_size: Optional[int] = None) -> str:
        """创建监听器（同步）"""
        future = asyncio.run_coroutine_threadsafe(
            self._client.create_listener(buffer_size), self._loop
        )
        return future.result(timeout=10)

    def remove_listener(self, listener_id: str):
        """移除监听器（同步）"""
        future = asyncio.run_coroutine_threadsafe(
            self._client.remove_listener(listener_id), self._loop
        )
        future.result(timeout=10)

    def get_message(
        self, listener_id: str, timeout: Optional[float] = None
    ) -> Tuple[Any, MessageType]:
        """获取消息（同步阻塞）"""
        future = asyncio.run_coroutine_threadsafe(
            self._client.get_message(listener_id, timeout), self._loop
        )
        return future.result(timeout=timeout)

    def get_message_nowait(self, listener_id: str) -> Optional[Tuple[Any, MessageType]]:
        """非阻塞获取消息（同步）"""
        return self._client.get_message_nowait(listener_id)

    def send(self, message: Union[str, bytes, Dict]):
        """发送消息（同步）"""
        future = asyncio.run_coroutine_threadsafe(
            self._client.send(message), self._loop
        )
        future.result(timeout=10)

    def get_metrics(self) -> Dict[str, Any]:
        """获取客户端指标（同步）"""
        future = asyncio.run_coroutine_threadsafe(
            self._client.get_metrics(), self._loop
        )
        return future.result(timeout=10)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# 使用示例
async def example_usage():
    """使用示例"""
    # 创建客户端
    client = AsyncWebSocketClient("wss://echo.websocket.org")

    async with client:
        # 创建监听器
        listener_id = await client.create_listener()

        # 发送消息
        await client.send("Hello, WebSocket!")

        # 接收消息（异步阻塞）
        try:
            message, msg_type = await client.get_message(listener_id, timeout=10)
            print(f"Received: {message}, type: {msg_type}")
        except asyncio.TimeoutError:
            print("Timeout waiting for message")

        # 或者使用异步迭代
        async for message, msg_type in client._listeners[listener_id]:
            print(f"Received: {message}, type: {msg_type}")
            break  # 只接收一条消息作为示例


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage())

"""

## 能力速览
1. 全异步 / 同步双形态
   AsyncWebSocketClient  —— 原生协程，性能高
   SyncWebSocketClient   —— 内部启线程+事件循环，给同步代码用

2. 监听器模式
   任意线程/协程可以“订阅”一个 listener_id，消息广播到所有监听器；
   每个监听器自带环形缓冲区，满时自动丢弃最旧数据，不会阻塞收发。

3. 全自动重连
   指数退避 + 随机抖动，可设最大次数或无限重连；
   网络闪断、压缩协商失败、服务端踢人都会自动重试。

4. 指标可观测
   连接次数、收发字节、队列长度、监听器数量一键导出，方便接入 Prometheus。

------------------------------------------------

## API 一张表
| 目标 | 异步用法 | 同步用法 | 备注 |
|---|---|---|---|
| 启动 | `async with client:` 或 `await client.start()` | `ws.start()` | 同步版启动后事件循环在后台线程跑 |
| 发消息 | `await client.send(dict/text/bytes)` | `ws.send(...)` | 队列满抛 `WebSocketError` |
| 收消息 | `await client.get_message(lid, timeout=10)` | `ws.get_message(lid, timeout=10)` | 超时抛 `asyncio.TimeoutError` |
| 非阻塞收 | `client._listeners[lid].get_nowait()` | `ws.get_message_nowait(lid)` | 无数据返回 None |
| 关闭 | 自动 / `await client.stop()` | `ws.stop()` | 会等待内部任务结束，线程安全 |
| 指标 | `client.get_metrics()` | `ws.get_metrics()` | 实时 Dict，含连接、重连、监听器数量 |

------------------------------------------------
## 踩坑提示
1. 监听器用完务必 `remove_listener`，否则一直占内存；
   当监听器数达到 `max_listeners` 会自动淘汰最旧的，可日志里看到 `Evicted`。

2. 发送队列满默认抛异常；如果想“覆盖旧数据”而不是抛错，把 `_send_queue` 换成环形队列即可，源码位置已留注释。

3. 同步版 `get_message` 的 `timeout` 是“从调用到返回”的总时长，包含线程调度时间，设太短容易超时。

4. 服务端如果发超大二进制帧，记得把 `receive_timeout` 适当调大，否则半截没收到就会触发重连。

5. 压缩协商失败（zlib wbits 错误）客户端会自动关闭压缩再重连一次，无需人工干预。

------------------------------------------------

"""
