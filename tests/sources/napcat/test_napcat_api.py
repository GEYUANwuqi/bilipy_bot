"""NapCat API 请求关联与资源清理测试（PERF-001）."""

import asyncio
from typing import Any, cast

import pytest

from butter_bot.sources.napcat.api.napcat_api import NapcatClient


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
