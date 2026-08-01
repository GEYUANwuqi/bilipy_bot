"""Tests for the WebSocket transport layer (ASYNC-002 / ASYNC-003).

这些用例全部离线运行：需要"连不上"的场景用一个刚释放的本地端口，
连接必定被拒绝且失败得很快。
"""

import asyncio
import socket

import pytest

from butterbot.utils.websocket import (
    AsyncWebSocketClient,
    ConnectionHealthState,
    ListenerClosedError,
    ListenerEvictedError,
    MessageType,
    ReconnectionStrategy,
    WebSocketConfig,
    WebSocketListener,
    WebSocketState,
)
from butterbot.utils.websocket import (
    ConnectionError as WsConnectionError,
)


def _closed_port_uri() -> str:
    """返回一个指向已关闭端口的 ws:// 地址（连接必定被拒绝）."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return "ws://127.0.0.1:%d" % port


def _client(**overrides) -> AsyncWebSocketClient:
    """构造一个参数偏小、失败很快的客户端."""
    kwargs = {
        "uri": _closed_port_uri(),
        "heartbeat": 1.0,
        "receive_timeout": 0.2,
        "connect_timeout": 0.2,
        "session_timeout": 1.0,
        "backoff_base": 0.01,
        "backoff_max": 0.05,
        "jitter_factor": 0.0,
        "reconnect_attempts": 1,
    }
    kwargs.update(overrides)
    return AsyncWebSocketClient(**kwargs)  # type: ignore[arg-type]


class TestWebSocketListenerClose:
    """close() 必须唤醒已经阻塞在 get() 上的消费者（ASYNC-003）."""

    @pytest.mark.asyncio
    async def test_close_wakes_blocked_getter(self):
        """等待中的 get() 应在 close() 后抛 ListenerClosedError 而非永久挂住."""
        listener = WebSocketListener(buffer_size=4)
        getter = asyncio.create_task(listener.get())
        await asyncio.sleep(0)  # 让 getter 真正阻塞在 queue.get()

        listener.close()

        with pytest.raises(ListenerClosedError):
            await asyncio.wait_for(getter, timeout=1.0)

    @pytest.mark.asyncio
    async def test_close_wakes_multiple_getters(self):
        """哨兵会被放回队列，多个等待者都应被唤醒."""
        listener = WebSocketListener(buffer_size=4)
        getters = [asyncio.create_task(listener.get()) for _ in range(3)]
        await asyncio.sleep(0)

        listener.close()

        results = await asyncio.wait_for(
            asyncio.gather(*getters, return_exceptions=True), timeout=1.0
        )
        assert all(isinstance(r, ListenerClosedError) for r in results)

    @pytest.mark.asyncio
    async def test_get_after_close_raises(self):
        """已关闭的监听器再 get 应直接抛异常."""
        listener = WebSocketListener()
        listener.close()
        with pytest.raises(ListenerClosedError):
            await listener.get()

    def test_get_nowait_after_close_raises(self):
        """get_nowait 在关闭后同样应抛异常."""
        listener = WebSocketListener()
        listener.close()
        with pytest.raises(ListenerClosedError):
            listener.get_nowait()

    def test_close_is_idempotent(self):
        """重复 close 不应抛出异常."""
        listener = WebSocketListener()
        listener.close()
        listener.close()
        assert listener.is_closed

    @pytest.mark.asyncio
    async def test_normal_message_still_delivered(self):
        """哨兵机制不应影响正常消息的投递."""
        listener = WebSocketListener()
        await listener.put("hello", MessageType.Text)
        message, msg_type = await listener.get(timeout=1.0)
        assert message == "hello"
        assert msg_type is MessageType.Text

    @pytest.mark.asyncio
    async def test_async_iteration_stops_on_close(self):
        """异步迭代应在 close 后正常终止（StopAsyncIteration）."""
        listener = WebSocketListener()
        await listener.put("a", MessageType.Text)
        listener_iter = listener.__aiter__()
        first = await listener_iter.__anext__()
        assert first[0] == "a"

        listener.close()
        collected = [item async for item in listener]
        assert collected == []


class TestListenerEviction:
    """监听器数量达上限时的淘汰不能死锁（ASYNC-002）."""

    @pytest.mark.asyncio
    async def test_eviction_does_not_deadlock(self):
        """超过 max_listeners 时创建监听器必须能返回.

        回归点：淘汰逻辑原本在持有非重入 threading.Lock 时调用
        remove_listener，会重入同一把锁 —— 整个事件循环线程永久挂死
        （不是超时，是硬死锁）。
        """
        client = _client(max_listeners=2)
        first = await client.create_listener()
        second = await client.create_listener()

        third = await asyncio.wait_for(client.create_listener(), timeout=2.0)

        assert first not in client._listeners
        assert second in client._listeners
        assert third in client._listeners

    @pytest.mark.asyncio
    async def test_eviction_keeps_listener_count_bounded(self):
        """连续创建远超上限的监听器，数量应始终不超过上限."""
        client = _client(max_listeners=3)
        for _ in range(10):
            await asyncio.wait_for(client.create_listener(), timeout=2.0)
        assert len(client._listeners) <= 3

    @pytest.mark.asyncio
    async def test_evicted_listener_is_closed(self):
        """被淘汰的监听器应被关闭，其等待者会醒来."""
        client = _client(max_listeners=1)
        first_id = await client.create_listener()
        first = client._listeners[first_id]

        await client.create_listener()

        assert first.is_closed

    @pytest.mark.asyncio
    async def test_get_message_on_evicted_listener_raises(self):
        """从已淘汰的监听器取消息应抛 ListenerEvictedError."""
        client = _client(max_listeners=1)
        first_id = await client.create_listener()
        await client.create_listener()

        with pytest.raises(ListenerEvictedError):
            await client.get_message(first_id, timeout=0.1)

    @pytest.mark.asyncio
    async def test_remove_listener_closes_it(self):
        """remove_listener 应关闭监听器并从表中摘除."""
        client = _client()
        listener_id = await client.create_listener()
        listener = client._listeners[listener_id]

        await client.remove_listener(listener_id)

        assert listener.is_closed
        assert listener_id not in client._listeners

    @pytest.mark.asyncio
    async def test_broadcast_reaches_all_listeners(self):
        """广播应投递到所有活跃监听器."""
        client = _client()
        ids = [await client.create_listener() for _ in range(3)]

        await client._broadcast_message("payload", MessageType.Text)

        for listener_id in ids:
            message, msg_type = await client.get_message(listener_id, timeout=1.0)
            assert message == "payload"
            assert msg_type is MessageType.Text


class TestReconnectionStrategy:
    """reconnect_attempts=0 的语义必须与文档一致（ASYNC-003）."""

    def test_zero_means_unlimited(self):
        """0 应表示无限重连，而不是一次都不试."""
        strategy = ReconnectionStrategy(
            WebSocketConfig(uri="ws://localhost:1", reconnect_attempts=0)
        )
        for _ in range(50):
            assert strategy.should_reconnect()
            strategy.on_attempt()

    def test_finite_limit_respected(self):
        """有限次数应在用满后停止."""
        strategy = ReconnectionStrategy(
            WebSocketConfig(uri="ws://localhost:1", reconnect_attempts=3)
        )
        for _ in range(3):
            assert strategy.should_reconnect()
            strategy.on_attempt()
        assert not strategy.should_reconnect()

    def test_first_attempt_has_no_delay(self):
        """首次尝试的退避应为 0（立即连接）."""
        strategy = ReconnectionStrategy(
            WebSocketConfig(uri="ws://localhost:1", jitter_factor=0.0)
        )
        assert strategy.get_delay() == 0.0

    def test_delay_grows_exponentially(self):
        """退避应指数增长并受 backoff_max 限制."""
        strategy = ReconnectionStrategy(
            WebSocketConfig(
                uri="ws://localhost:1",
                backoff_base=1.0,
                backoff_max=4.0,
                jitter_factor=0.0,
            )
        )
        strategy.on_attempt()
        assert strategy.get_delay() == 1.0
        strategy.on_attempt()
        assert strategy.get_delay() == 2.0
        strategy.on_attempt()
        assert strategy.get_delay() == 4.0
        strategy.on_attempt()
        assert strategy.get_delay() == 4.0  # 被 backoff_max 截断

    def test_on_success_resets(self):
        """连接成功应重置计数器."""
        strategy = ReconnectionStrategy(
            WebSocketConfig(uri="ws://localhost:1", reconnect_attempts=2)
        )
        strategy.on_attempt()
        strategy.on_attempt()
        assert not strategy.should_reconnect()
        strategy.on_success()
        assert strategy.should_reconnect()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("receive_timeout", 0),
        ("connect_timeout", 0),
        ("send_queue_size", 0),
        ("session_timeout", 0),
        ("backoff_base", -1),
        ("jitter_factor", -1),
        ("compression", 16),
        ("max_listeners", 0),
        ("listener_buffer_size", 0),
    ],
)
def test_invalid_websocket_config_is_rejected(field, value):
    kwargs = {"uri": "ws://localhost:1", field: value}
    with pytest.raises(ValueError):
        WebSocketConfig(**kwargs)  # type: ignore[arg-type]


def test_backoff_max_cannot_be_less_than_base():
    with pytest.raises(ValueError, match="Backoff max"):
        WebSocketConfig(
            uri="ws://localhost:1",
            backoff_base=2.0,
            backoff_max=1.0,
        )


class TestClientShutdown:
    """首连失败也要走重连策略，且退出时必须释放资源（ASYNC-003）."""

    @pytest.mark.asyncio
    async def test_first_connect_failure_uses_reconnect_strategy(self):
        """首连失败应被重连策略接管（原实现首连在 while 之外，策略完全不生效）."""
        client = _client(reconnect_attempts=3)
        await client.start()

        # 等主循环把 3 次尝试用完后自行退出
        for _ in range(200):
            if not client.running:
                break
            await asyncio.sleep(0.02)

        assert client.reconnection.attempt_count == 3
        assert not client.running

    @pytest.mark.asyncio
    async def test_exhausted_reconnect_releases_session(self):
        """重连用尽后 aiohttp session 必须被释放，不能泄漏.

        回归点：原实现在 _handle_disconnected 里 `await self.stop()`，
        而 stop 内部 `await self._main_task` 就是在 await 主任务自己；
        异常传出后 finally 的再次 stop() 被开头的早退挡掉，
        监听器与 session 全部泄漏。
        """
        client = _client(reconnect_attempts=1)
        await client.create_listener()
        await client.start()

        for _ in range(200):
            if not client.running:
                break
            await asyncio.sleep(0.02)

        assert not client.running
        assert client.connection.session is None
        assert client.connection.websocket is None
        assert client.connection.state is WebSocketState.Closed
        assert client._listeners == {}

    @pytest.mark.asyncio
    async def test_external_stop_terminates_main_task(self):
        """外部 stop 应取消主任务并完成清理."""
        client = _client(reconnect_attempts=0)  # 无限重连，只能由外部停止
        await client.start()
        await asyncio.sleep(0.05)
        assert client.running

        await asyncio.wait_for(client.stop(), timeout=3.0)

        assert not client.running
        assert client.connection.session is None
        assert client._listeners == {}

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        """重复 stop 不应抛出异常."""
        client = _client(reconnect_attempts=0)
        await client.start()
        await asyncio.wait_for(client.stop(), timeout=3.0)
        await asyncio.wait_for(client.stop(), timeout=3.0)
        assert not client.running

    @pytest.mark.asyncio
    async def test_stop_closes_listeners(self):
        """stop 应关闭全部监听器，唤醒它们的等待者."""
        client = _client(reconnect_attempts=0)
        listener_id = await client.create_listener()
        listener = client._listeners[listener_id]
        await client.start()

        await asyncio.wait_for(client.stop(), timeout=3.0)

        assert listener.is_closed

    @pytest.mark.asyncio
    async def test_unlimited_reconnect_keeps_retrying(self):
        """reconnect_attempts=0 时应持续重试而不是立即放弃."""
        client = _client(reconnect_attempts=0)
        await client.start()

        for _ in range(200):
            if client.reconnection.attempt_count >= 2:
                break
            await asyncio.sleep(0.02)

        assert client.reconnection.attempt_count >= 2
        assert client.running
        await asyncio.wait_for(client.stop(), timeout=3.0)

    @pytest.mark.asyncio
    async def test_send_before_running_raises(self):
        """未启动时发送应抛 ConnectionError."""
        client = _client()
        with pytest.raises(WsConnectionError):
            await client.send("hi")

    @pytest.mark.asyncio
    async def test_metrics_report_failed_connections(self):
        """指标应记录失败的连接尝试."""
        client = _client(reconnect_attempts=2)
        await client.start()

        for _ in range(200):
            if not client.running:
                break
            await asyncio.sleep(0.02)

        metrics = client.get_metrics()
        assert metrics["connection"]["failed_connections"] >= 1
        assert metrics["running"] is False


class TestClientReadiness:
    """start 必须明确区分“任务已创建”与“首次连接就绪”."""

    @pytest.mark.asyncio
    async def test_start_can_return_without_waiting_for_ready(self):
        client = _client(reconnect_attempts=0)

        await client.start(wait_ready=False)

        assert client.running
        assert not client.ready
        assert client.health.state is ConnectionHealthState.STARTING
        await client.stop()

    @pytest.mark.asyncio
    async def test_wait_ready_propagates_final_connection_failure(self):
        client = _client(reconnect_attempts=2)

        with pytest.raises(WsConnectionError, match="Connection failed"):
            await client.start(wait_ready=True, ready_timeout=2.0)

        assert not client.running
        assert not client.ready
        assert client.health.state is ConnectionHealthState.STOPPED
        assert client.health.last_error_type == "ConnectionError"

    @pytest.mark.asyncio
    async def test_wait_until_ready_observes_first_success(self, monkeypatch):
        client = _client(reconnect_attempts=1)
        connected = False
        blocked = asyncio.Event()

        async def connect() -> None:
            nonlocal connected
            connected = True
            client.connection.state = WebSocketState.CONNECTED

        monkeypatch.setattr(client.connection, "connect", connect)
        monkeypatch.setattr(
            client.connection,
            "is_connected",
            lambda: connected,
        )
        monkeypatch.setattr(client, "_process_send_queue", blocked.wait)
        monkeypatch.setattr(client, "_process_receive", blocked.wait)

        await client.start(wait_ready=False)
        await client.wait_until_ready(timeout=1.0)

        assert client.ready
        assert client.health.state is ConnectionHealthState.READY
        assert client.health.last_success_at is not None
        await client.stop()

    @pytest.mark.asyncio
    async def test_ready_timeout_stops_fresh_client_transactionally(self):
        client = _client(
            reconnect_attempts=0,
            backoff_base=1.0,
            backoff_max=1.0,
        )

        with pytest.raises(WsConnectionError, match="ready timeout"):
            await client.start(wait_ready=True, ready_timeout=0.01)

        assert not client.running
        assert client._main_task is None
        assert client.connection.session is None
