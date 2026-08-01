"""本地 aiohttp WebSocket 协议级回归，不访问外网."""

import asyncio
import json
import socket
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from aiohttp import web

from butterbot.sources.napcat.api.napcat_api import NapcatClient
from butterbot.utils.websocket import (
    AsyncWebSocketClient,
    MessageType,
)
from butterbot.utils.websocket import (
    ConnectionError as WebSocketConnectionError,
)

WebSocketHandler = Callable[[web.Request], Awaitable[web.StreamResponse]]


@asynccontextmanager
async def websocket_server(handler: WebSocketHandler) -> AsyncIterator[str]:
    """在随机本地端口运行一个可控 WebSocket 服务器."""
    app = web.Application()
    app.router.add_get("/ws", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(socket.SOMAXCONN)
    server_socket.setblocking(False)
    port = server_socket.getsockname()[1]
    site = web.SockSite(runner, server_socket)
    await site.start()
    try:
        yield "ws://127.0.0.1:%s/ws" % port
    finally:
        await runner.cleanup()


def _client(uri: str, **overrides: Any) -> AsyncWebSocketClient:
    options: dict[str, Any] = {
        "uri": uri,
        "heartbeat": 1.0,
        "receive_timeout": 0.2,
        "connect_timeout": 0.2,
        "session_timeout": 2.0,
        "backoff_base": 0.01,
        "backoff_max": 0.02,
        "jitter_factor": 0.0,
        "reconnect_attempts": 3,
    }
    options.update(overrides)
    return AsyncWebSocketClient(**options)


class TestWebSocketProtocol:
    @pytest.mark.asyncio
    async def test_ready_and_text_delivery_over_real_socket(self) -> None:
        async def handler(request: web.Request) -> web.StreamResponse:
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_str("hello")
            async for _ in ws:
                pass
            return ws

        async with websocket_server(handler) as uri:
            client = _client(uri)
            listener = await client.create_listener()
            try:
                await asyncio.wait_for(
                    client.start(wait_ready=True, ready_timeout=1.0),
                    timeout=2.0,
                )
                message, message_type = await client.get_message(
                    listener,
                    timeout=1.0,
                )
                assert message == "hello"
                assert message_type is MessageType.Text
            finally:
                await asyncio.wait_for(client.stop(), timeout=2.0)

            assert client.connection.session is None
            assert client.connection.websocket is None
            assert client._main_task is None

    @pytest.mark.asyncio
    async def test_http_handshake_failure_propagates_after_retries(self) -> None:
        attempts = 0

        async def handler(request: web.Request) -> web.StreamResponse:
            nonlocal attempts
            attempts += 1
            return web.Response(status=503, text="not ready")

        async with websocket_server(handler) as uri:
            client = _client(uri, reconnect_attempts=2)
            try:
                with pytest.raises(WebSocketConnectionError):
                    await asyncio.wait_for(
                        client.start(wait_ready=True, ready_timeout=1.0),
                        timeout=2.0,
                    )
            finally:
                await asyncio.wait_for(client.stop(), timeout=2.0)

            assert attempts == 2
            assert not client.running
            assert client.connection.session is None

    @pytest.mark.asyncio
    async def test_server_close_reconnects_to_second_socket(self) -> None:
        connections = 0
        second_connected = asyncio.Event()

        async def handler(request: web.Request) -> web.StreamResponse:
            nonlocal connections
            connections += 1
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            if connections == 1:
                await ws.close()
                return ws
            second_connected.set()
            async for _ in ws:
                pass
            return ws

        async with websocket_server(handler) as uri:
            client = _client(uri)
            try:
                await asyncio.wait_for(
                    client.start(wait_ready=True, ready_timeout=1.0),
                    timeout=2.0,
                )
                await asyncio.wait_for(second_connected.wait(), timeout=2.0)
                for _ in range(100):
                    if client.ready:
                        break
                    await asyncio.sleep(0.01)

                assert connections >= 2
                assert client.ready
            finally:
                await asyncio.wait_for(client.stop(), timeout=2.0)

    @pytest.mark.asyncio
    async def test_listener_backpressure_drops_oldest_messages(self) -> None:
        sent = asyncio.Event()

        async def handler(request: web.Request) -> web.StreamResponse:
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            for index in range(5):
                await ws.send_str(str(index))
            sent.set()
            async for _ in ws:
                pass
            return ws

        async with websocket_server(handler) as uri:
            client = _client(uri)
            listener = await client.create_listener(buffer_size=2)
            try:
                await asyncio.wait_for(
                    client.start(wait_ready=True, ready_timeout=1.0),
                    timeout=2.0,
                )
                await asyncio.wait_for(sent.wait(), timeout=1.0)
                await asyncio.sleep(0.05)

                first = await client.get_message(listener, timeout=1.0)
                second = await client.get_message(listener, timeout=1.0)
                assert [first[0], second[0]] == ["3", "4"]
            finally:
                await asyncio.wait_for(client.stop(), timeout=2.0)


class TestNapcatProtocol:
    @pytest.mark.asyncio
    async def test_malformed_json_does_not_stop_next_event(self) -> None:
        received: list[dict[str, Any]] = []

        async def handler(request: web.Request) -> web.StreamResponse:
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_str("{broken-json")
            await ws.send_json({"post_type": "meta_event", "value": 1})
            async for _ in ws:
                pass
            return ws

        async with websocket_server(handler) as uri:
            client = NapcatClient(
                uri,
                reconnect_attempts=2,
                receive_timeout=0.2,
                ready_timeout=1.0,
            )

            async def on_event(message: dict[str, Any]) -> None:
                received.append(message)

            client.set_handler(on_event)
            try:
                await asyncio.wait_for(client.start(), timeout=2.0)
                for _ in range(100):
                    if received:
                        break
                    await asyncio.sleep(0.01)

                assert received == [{"post_type": "meta_event", "value": 1}]
            finally:
                await asyncio.wait_for(client.stop(), timeout=2.0)

            assert client._task is None
            assert client._listener_id is None
            assert not client.cleanup_required

    @pytest.mark.asyncio
    async def test_echo_response_and_timeout_cleanup(self) -> None:
        async def handler(request: web.Request) -> web.StreamResponse:
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            async for message in ws:
                payload = json.loads(message.data)
                if payload.get("action") == "echo":
                    await ws.send_json({"echo": payload["echo"], "data": "ok"})
            return ws

        async with websocket_server(handler) as uri:
            client = NapcatClient(
                uri,
                reconnect_attempts=2,
                receive_timeout=0.05,
                ready_timeout=1.0,
            )

            async def on_event(message: dict[str, Any]) -> None:
                pass

            client.set_handler(on_event)
            try:
                await asyncio.wait_for(client.start(), timeout=2.0)

                response = await client.send_request({"action": "echo"})
                assert response is not None and response["data"] == "ok"
                with pytest.raises(TimeoutError):
                    await client.send_request({"action": "ignore"})
                assert client.pending_requests == 0
            finally:
                await asyncio.wait_for(client.stop(), timeout=2.0)

            assert client.client.connection.session is None
