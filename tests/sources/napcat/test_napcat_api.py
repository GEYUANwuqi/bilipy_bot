"""NapCat API 请求关联与资源清理测试（PERF-001）."""

import asyncio
from typing import Any, cast

import pytest

from butterbot.sources.napcat.api.napcat_api import NapcatClient, NapcatConfig
from butterbot.utils.websocket import ConnectionError, ListenerId


class SendOnlyTransport:
    """只记录发送内容的传输桩，响应由测试按 echo 显式注入."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.sent_event = asyncio.Event()
        self.stopped = False

    async def send(self, message: dict[str, Any]) -> None:
        self.sent.append(dict(message))
        self.sent_event.set()

    async def stop(self) -> None:
        self.stopped = True


def _client(timeout: float = 1.0) -> tuple[NapcatClient, SendOnlyTransport]:
    client = NapcatClient("ws://localhost:3001", receive_timeout=timeout)
    transport = SendOnlyTransport()
    # 该测试只覆盖 send 路径，桩不需要实现完整 WebSocket 客户端接口。
    client.client = cast(Any, transport)
    return client, transport


class TestRequestCorrelation:
    @pytest.mark.asyncio
    async def test_concurrent_responses_are_correlated_by_echo_out_of_order(
        self,
    ) -> None:
        """并发响应乱序到达时仍应回到各自请求，且不创建广播 listener."""
        client, transport = _client()

        first = asyncio.create_task(client.send_request({"action": "first"}))
        second = asyncio.create_task(client.send_request({"action": "second"}))
        while len(transport.sent) < 2:
            transport.sent_event.clear()
            await transport.sent_event.wait()

        first_echo = transport.sent[0]["echo"]
        second_echo = transport.sent[1]["echo"]
        assert first_echo != second_echo

        assert client._resolve_response({"echo": second_echo, "data": "second"})
        assert client._resolve_response({"echo": first_echo, "data": "first"})

        assert await first == {"echo": first_echo, "data": "first"}
        assert await second == {"echo": second_echo, "data": "second"}
        assert client.pending_requests == 0

    @pytest.mark.asyncio
    async def test_timeout_removes_pending_future(self) -> None:
        """请求超时后不能在 pending 表中留下 Future."""
        client, _transport = _client(timeout=0.001)

        with pytest.raises(TimeoutError):
            await client.send_request({"action": "timeout"})

        assert client.pending_requests == 0

    @pytest.mark.asyncio
    async def test_cancellation_removes_pending_future(self) -> None:
        """调用方取消请求时应传播取消并清理 pending 表."""
        client, transport = _client()
        task = asyncio.create_task(client.send_request({"action": "cancel"}))
        await transport.sent_event.wait()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert client.pending_requests == 0

    @pytest.mark.asyncio
    async def test_stop_cancels_all_waiting_requests(self) -> None:
        """客户端停止时应唤醒并取消全部请求等待者."""
        client, transport = _client()
        task = asyncio.create_task(client.send_request({"action": "pending"}))
        await transport.sent_event.wait()

        await client.stop()

        with pytest.raises(asyncio.CancelledError):
            await task
        assert transport.stopped
        assert client.pending_requests == 0

    def test_unknown_echo_is_not_consumed(self) -> None:
        """未知 echo 应留给普通事件处理路径."""
        client, _transport = _client()
        assert not client._resolve_response({"echo": "unknown"})


class LifecycleTransport:
    """用于验证 NapcatClient 启停事务的传输层桩."""

    def __init__(self) -> None:
        self.running = False
        self.ready = False
        self.calls: list[str] = []
        self.start_calls = 0
        self.stop_calls = 0
        self.remove_calls = 0
        self.ready_error: BaseException | None = None
        self.remove_error: BaseException | None = None
        self._message_wait = asyncio.Event()

    async def create_listener(self) -> ListenerId:
        self.calls.append("listener")
        return ListenerId("listener-1")

    async def start(self, *, wait_ready: bool = False) -> None:
        assert not wait_ready
        self.calls.append("start")
        self.start_calls += 1
        self.running = True

    async def wait_until_ready(self, timeout: float | None = None) -> None:
        self.calls.append("ready")
        if self.ready_error is not None:
            raise self.ready_error
        self.ready = True

    async def get_message(self, listener_id, timeout):
        await self._message_wait.wait()
        raise AssertionError("test transport should be cancelled")

    async def remove_listener(self, listener_id: ListenerId) -> None:
        self.calls.append("remove")
        self.remove_calls += 1
        if self.remove_error is not None:
            raise self.remove_error

    async def stop(self) -> None:
        self.calls.append("stop")
        self.stop_calls += 1
        self.running = False
        self.ready = False


def _lifecycle_client() -> tuple[NapcatClient, LifecycleTransport]:
    client = NapcatClient("ws://localhost:3001", ready_timeout=0.1)
    transport = LifecycleTransport()
    client.client = cast(Any, transport)

    async def handler(message: dict[str, Any]) -> None:
        pass

    client.set_handler(handler)
    return client, transport


class TestNapcatClientLifecycle:
    def test_ready_timeout_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="ready_timeout"):
            NapcatConfig(url="ws://localhost:3001", ready_timeout=0)

    @pytest.mark.asyncio
    async def test_start_waits_for_ready_and_orders_listener_first(self) -> None:
        client, transport = _lifecycle_client()

        await client.start()

        assert transport.calls[:3] == ["listener", "start", "ready"]
        assert client.running
        assert client.ready
        assert client._task is not None
        await client.stop()

    @pytest.mark.asyncio
    async def test_start_failure_rolls_back_all_partial_resources(self) -> None:
        client, transport = _lifecycle_client()
        original = ConnectionError("首连失败")
        transport.ready_error = original

        with pytest.raises(ConnectionError) as exc_info:
            await client.start()

        assert exc_info.value is original
        assert not client.running
        assert client._task is None
        assert client._listener_id is None
        assert transport.remove_calls == 1
        assert transport.stop_calls == 1

    @pytest.mark.asyncio
    async def test_start_and_stop_are_idempotent(self) -> None:
        client, transport = _lifecycle_client()

        await client.start()
        await client.start()
        await client.stop()
        await client.stop()

        assert transport.start_calls == 1
        assert transport.remove_calls == 1
        assert transport.stop_calls == 1

    @pytest.mark.asyncio
    async def test_stop_still_closes_transport_if_listener_removal_fails(self) -> None:
        client, transport = _lifecycle_client()
        await client.start()
        transport.remove_error = RuntimeError("退订失败")

        with pytest.raises(RuntimeError, match="退订失败"):
            await client.stop()

        assert transport.stop_calls == 1
        assert client._listener_id is not None

        transport.remove_error = None
        await client.stop()
        assert client._listener_id is None
        assert not client.cleanup_required
