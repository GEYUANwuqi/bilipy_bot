"""NapCat API 请求关联与资源清理测试（PERF-001）."""

import asyncio
from typing import Any, Literal, cast

import pytest

from butterbot.sources.napcat.api import NapcatApi
from butterbot.sources.napcat.api.napcat_api import NapcatClient, NapcatConfig
from butterbot.sources.napcat.data import (
    NapcatForwardMessageBuilder,
    NapcatMessageBuilder,
)
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


class TestNapcatApi:
    @pytest.mark.asyncio
    async def test_call_action_wraps_action_and_params(self) -> None:
        """Action 调用应统一封装协议请求。"""
        api = object.__new__(NapcatApi)
        requests: list[dict[str, Any]] = []

        async def send_request(request: dict) -> dict:
            requests.append(request)
            return {"status": "ok"}

        api.send_request = send_request  # type: ignore[method-assign]

        result = await api.call_action("test_action", value=1, enabled=True)

        assert result == {"status": "ok"}
        assert requests == [
            {
                "action": "test_action",
                "params": {"value": 1, "enabled": True},
            }
        ]

    @pytest.mark.asyncio
    async def test_send_group_message_accepts_napcat_message(self) -> None:
        """发送接口应将领域消息转换为 OneBot11 段字典。"""
        api = object.__new__(NapcatApi)
        requests: list[dict[str, Any]] = []

        async def send_request(request: dict) -> dict:
            requests.append(request)
            return {"status": "ok"}

        api.send_request = send_request  # type: ignore[method-assign]

        result = await api.send_group_message(
            123456,
            NapcatMessageBuilder().text("测试消息").build(),
        )

        assert result == {"status": "ok"}
        assert requests == [
            {
                "action": "send_group_msg",
                "params": {
                    "group_id": 123456,
                    "message": [{"type": "text", "data": {"text": "测试消息"}}],
                },
            }
        ]

    @pytest.mark.asyncio
    async def test_send_private_message_accepts_napcat_message(self) -> None:
        """私聊发送接口应复用领域消息序列化。"""
        api = object.__new__(NapcatApi)
        calls: list[tuple[str, dict[str, Any]]] = []

        async def call_action(action: str, **params: Any) -> dict:
            calls.append((action, params))
            return {"status": "ok"}

        api.call_action = call_action  # type: ignore[method-assign]

        result = await api.send_private_message(
            123456,
            NapcatMessageBuilder().text("私聊消息").build(),
        )

        assert result == {"status": "ok"}
        assert calls == [
            (
                "send_private_msg",
                {
                    "user_id": 123456,
                    "message": [{"type": "text", "data": {"text": "私聊消息"}}],
                },
            )
        ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method_name", "kwargs", "action", "expected_params"),
        [
            (
                "send_private_message",
                {"user_id": 1, "message": [{"type": "text", "data": {}}]},
                "send_private_msg",
                {"user_id": 1, "message": [{"type": "text", "data": {}}]},
            ),
            ("delete_message", {"message_id": 2}, "delete_msg", {"message_id": 2}),
            ("send_like", {"user_id": 3}, "send_like", {"user_id": 3, "times": 1}),
            (
                "set_message_emoji_like",
                {"message_id": 4, "emoji_id": "14", "set": False},
                "set_msg_emoji_like",
                {"message_id": 4, "emoji_id": "14", "set": False},
            ),
            (
                "mark_group_messages_as_read",
                {"group_id": 5},
                "mark_group_msg_as_read",
                {"group_id": 5},
            ),
            (
                "mark_private_messages_as_read",
                {"user_id": 6},
                "mark_private_msg_as_read",
                {"user_id": 6},
            ),
            (
                "send_poke",
                {"group_id": 7, "user_id": 8},
                "send_poke",
                {"group_id": 7, "user_id": 8},
            ),
            ("friend_poke", {"user_id": 9}, "friend_poke", {"user_id": 9}),
            ("get_login_info", {}, "get_login_info", {}),
            (
                "get_stranger_info",
                {"user_id": 10},
                "get_stranger_info",
                {"user_id": 10},
            ),
            ("get_friend_list", {}, "get_friend_list", {}),
            ("get_group_list", {}, "get_group_list", {}),
            (
                "get_group_info",
                {"group_id": 11},
                "get_group_info",
                {"group_id": 11},
            ),
            (
                "get_group_member_info",
                {"group_id": 12, "user_id": 13},
                "get_group_member_info",
                {"group_id": 12, "user_id": 13},
            ),
            (
                "get_group_member_list",
                {"group_id": 14},
                "get_group_member_list",
                {"group_id": 14},
            ),
            ("get_message", {"message_id": 15}, "get_msg", {"message_id": 15}),
            (
                "get_group_message_history",
                {"group_id": 16, "message_seq": 17, "count": 10},
                "get_group_msg_history",
                {"group_id": 16, "message_seq": 17, "count": 10},
            ),
            (
                "get_private_message_history",
                {"user_id": 18},
                "get_friend_msg_history",
                {"user_id": 18, "count": 20},
            ),
            ("get_status", {}, "get_status", {}),
            ("get_version_info", {}, "get_version_info", {}),
            (
                "set_group_kick",
                {"group_id": 19, "user_id": 20},
                "set_group_kick",
                {"group_id": 19, "user_id": 20, "reject_add_request": False},
            ),
            (
                "set_group_ban",
                {"group_id": 21, "user_id": 22},
                "set_group_ban",
                {"group_id": 21, "user_id": 22, "duration": 1800},
            ),
            (
                "set_group_whole_ban",
                {"group_id": 23},
                "set_group_whole_ban",
                {"group_id": 23, "enable": True},
            ),
            (
                "set_group_admin",
                {"group_id": 24, "user_id": 25, "enable": False},
                "set_group_admin",
                {"group_id": 24, "user_id": 25, "enable": False},
            ),
            (
                "set_group_card",
                {"group_id": 26, "user_id": 27, "card": "新名片"},
                "set_group_card",
                {"group_id": 26, "user_id": 27, "card": "新名片"},
            ),
            (
                "set_group_name",
                {"group_id": 28, "name": "新群名"},
                "set_group_name",
                {"group_id": 28, "group_name": "新群名"},
            ),
            (
                "set_group_leave",
                {"group_id": 29},
                "set_group_leave",
                {"group_id": 29, "is_dismiss": False},
            ),
            (
                "set_group_special_title",
                {"group_id": 30, "user_id": 31, "special_title": "头衔"},
                "set_group_special_title",
                {"group_id": 30, "user_id": 31, "special_title": "头衔"},
            ),
            (
                "set_friend_add_request",
                {"flag": "friend-flag"},
                "set_friend_add_request",
                {"flag": "friend-flag", "approve": True, "remark": ""},
            ),
            (
                "set_group_add_request",
                {"flag": "group-flag", "sub_type": "add", "approve": False},
                "set_group_add_request",
                {
                    "flag": "group-flag",
                    "sub_type": "add",
                    "approve": False,
                    "reason": "",
                },
            ),
        ],
    )
    async def test_high_frequency_api_maps_to_action(
        self,
        method_name: str,
        kwargs: dict[str, Any],
        action: str,
        expected_params: dict[str, Any],
    ) -> None:
        """高频 API 的公开参数应准确映射到 NapCat action。"""
        api = object.__new__(NapcatApi)
        calls: list[tuple[str, dict[str, Any]]] = []

        async def call_action(action: str, **params: Any) -> dict:
            calls.append((action, params))
            return {"status": "ok"}

        api.call_action = call_action  # type: ignore[method-assign]

        result = await getattr(api, method_name)(**kwargs)

        assert result == {"status": "ok"}
        assert calls == [(action, expected_params)]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("message_type", "target_id", "target_params"),
        [
            ("group", "123456", {"group_id": 123456}),
            ("private", 654321, {"user_id": 654321}),
        ],
    )
    async def test_send_forward_message_maps_target_and_nodes(
        self,
        message_type: Literal["group", "private"],
        target_id: str | int,
        target_params: dict[str, int],
    ) -> None:
        """转发接口应按会话类型映射目标并序列化节点。"""
        api = object.__new__(NapcatApi)
        calls: list[tuple[str, dict[str, Any]]] = []

        async def call_action(action: str, **params: Any) -> dict:
            calls.append((action, params))
            return {"status": "ok"}

        api.call_action = call_action  # type: ignore[method-assign]
        message = (
            NapcatForwardMessageBuilder(user_id=1, nickname="发送者")
            .forward(10001)
            .node(NapcatMessageBuilder().text("转发正文"))
            .build()
        )

        result = await api.send_forward_message(message_type, target_id, message)

        assert result == {"status": "ok"}
        assert calls == [
            (
                "send_forward_msg",
                {
                    "message_type": message_type,
                    "messages": [
                        {"type": "node", "data": {"id": "10001"}},
                        {
                            "type": "node",
                            "data": {
                                "user_id": "1",
                                "nickname": "发送者",
                                "content": [
                                    {
                                        "type": "text",
                                        "data": {"text": "转发正文"},
                                    }
                                ],
                            },
                        },
                    ],
                    **target_params,
                },
            )
        ]

    @pytest.mark.asyncio
    async def test_send_forward_message_rejects_unknown_message_type(self) -> None:
        """未知会话类型不能被错误地当作私聊发送。"""
        api = object.__new__(NapcatApi)
        message = NapcatForwardMessageBuilder().forward(10001).build()

        with pytest.raises(ValueError, match="不支持的转发消息类型"):
            await api.send_forward_message(cast(Any, "channel"), 123456, message)


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
    def test_create_uses_bearer_token_for_websocket_authorization(self) -> None:
        """NapCat 按 OneBot WebSocket 认证约定要求 Bearer 前缀。"""
        client = NapcatClient.create(
            NapcatConfig(url="ws://localhost:3001", token="test-token")
        )

        assert client.client.config.headers == {"Authorization": "Bearer test-token"}

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
