"""NapCat 事件数据便捷方法测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from butterbot.sources.napcat.api import NapcatApi
from butterbot.sources.napcat.data import (
    NapcatData,
    NapcatFriendRequestData,
    NapcatGroupMessageData,
    NapcatGroupRequestData,
    NapcatPrivateMessageData,
)


def _message(*, message_type: str = "group") -> dict[str, object]:
    raw: dict[str, object] = {
        "time": 1,
        "self_id": 10000,
        "post_type": "message",
        "message_type": message_type,
        "sub_type": "normal" if message_type == "group" else "friend",
        "message_id": 123,
        "user_id": 456,
        "message": [{"type": "text", "data": {"text": "hello"}}],
        "raw_message": "hello",
        "font": 0,
        "sender": {"user_id": 456, "nickname": "tester"},
    }
    if message_type == "group":
        raw["group_id"] = 789
    return raw


def _request(*, request_type: str) -> dict[str, object]:
    raw: dict[str, object] = {
        "time": 1,
        "self_id": 10000,
        "post_type": "request",
        "request_type": request_type,
        "flag": "request-flag",
        "user_id": 456,
        "comment": "hello",
    }
    if request_type == "group":
        raw.update(sub_type="add", group_id=789)
    return raw


def _bind(data: NapcatData, api: object) -> SimpleNamespace:
    registry = SimpleNamespace(get=lambda api_type, config_key: api)
    runtime = SimpleNamespace(api_ctx=registry, bus=object())
    data.bind_runtime(runtime, "qq_account")  # type: ignore[arg-type]
    return runtime


def test_runtime_properties_require_binding() -> None:
    data = NapcatData.model_validate(
        {"time": 1, "self_id": 10000, "post_type": "unknown"}
    )

    with pytest.raises(RuntimeError, match="runtime"):
        _ = data.runtime
    with pytest.raises(RuntimeError, match="config_key"):
        _ = data.config_key


@pytest.mark.asyncio
async def test_group_message_common_methods() -> None:
    data = NapcatData.from_dict(_message())
    assert isinstance(data, NapcatGroupMessageData)
    api = SimpleNamespace(
        send_group_message=AsyncMock(return_value={"status": "ok"}),
        delete_message=AsyncMock(return_value=None),
        set_message_emoji_like=AsyncMock(return_value=None),
        mark_group_messages_as_read=AsyncMock(return_value=None),
        send_poke=AsyncMock(return_value=None),
    )
    runtime = _bind(data, api)

    result = await data.reply("收到")
    await data.recall()
    await data.set_emoji_like(66, enabled=False)
    await data.mark_read()
    await data.poke()

    assert data.runtime is runtime
    assert data.bus is runtime.bus
    assert data.api is api
    assert result == {"status": "ok"}
    api.send_group_message.assert_awaited_once_with(
        789,
        [
            {"type": "reply", "data": {"id": "123"}},
            {"type": "text", "data": {"text": "收到"}},
        ],
    )
    api.delete_message.assert_awaited_once_with(123)
    api.set_message_emoji_like.assert_awaited_once_with(123, "66", set=False)
    api.mark_group_messages_as_read.assert_awaited_once_with(789)
    api.send_poke.assert_awaited_once_with(789, 456)


@pytest.mark.asyncio
async def test_private_message_common_methods_without_quote() -> None:
    data = NapcatData.from_dict(_message(message_type="private"))
    assert isinstance(data, NapcatPrivateMessageData)
    api = SimpleNamespace(
        send_private_message=AsyncMock(return_value=None),
        mark_private_messages_as_read=AsyncMock(return_value=None),
        friend_poke=AsyncMock(return_value=None),
        send_like=AsyncMock(return_value=None),
    )
    _bind(data, api)

    await data.reply("你好", quote=False)
    await data.mark_read()
    await data.poke()
    await data.like(times=3)

    api.send_private_message.assert_awaited_once_with(
        456,
        [{"type": "text", "data": {"text": "你好"}}],
    )
    api.mark_private_messages_as_read.assert_awaited_once_with(456)
    api.friend_poke.assert_awaited_once_with(456)
    api.send_like.assert_awaited_once_with(456, times=3)


@pytest.mark.asyncio
async def test_request_approve_and_reject_methods() -> None:
    friend = NapcatData.from_dict(_request(request_type="friend"))
    group = NapcatData.from_dict(_request(request_type="group"))
    assert isinstance(friend, NapcatFriendRequestData)
    assert isinstance(group, NapcatGroupRequestData)
    api = SimpleNamespace(
        set_friend_add_request=AsyncMock(return_value=None),
        set_group_add_request=AsyncMock(return_value=None),
    )
    _bind(friend, api)
    _bind(group, api)

    await friend.approve(remark="新好友")
    await friend.reject()
    await group.approve()
    await group.reject(reason="暂不接收")

    assert api.set_friend_add_request.await_args_list == [
        (("request-flag",), {"approve": True, "remark": "新好友"}),
        (("request-flag",), {"approve": False}),
    ]
    assert api.set_group_add_request.await_args_list == [
        (("request-flag", "add"), {"approve": True}),
        (
            ("request-flag", "add"),
            {"approve": False, "reason": "暂不接收"},
        ),
    ]


def test_api_property_uses_bound_config_key() -> None:
    data = NapcatData.from_dict(_message())
    calls = []
    api = object()
    registry = SimpleNamespace(
        get=lambda api_type, config_key: calls.append((api_type, config_key)) or api
    )
    runtime = SimpleNamespace(api_ctx=registry, bus=object())
    data.bind_runtime(runtime, "secondary")  # type: ignore[arg-type]

    assert data.api is api
    assert calls == [(NapcatApi, "secondary")]
