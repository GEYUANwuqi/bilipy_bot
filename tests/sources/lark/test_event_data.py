import pytest

from butterbot.sources.lark.data import (
    LarkData,
    LarkMenuData,
    LarkMessageReceiveData,
    LarkUnknownData,
    LarkUserAddedData,
)
from butterbot.sources.lark.types import LarkType


def _envelope(event_type: str, event: dict) -> dict:
    return {
        "schema": "2.0",
        "header": {
            "event_id": "event-1",
            "event_type": event_type,
            "create_time": "1720000000000",
            "tenant_key": "tenant",
            "app_id": "cli_test",
        },
        "event": event,
    }


def test_message_receive_is_dispatched_and_content_is_parsed() -> None:
    data = LarkData.from_envelope(
        _envelope(
            "im.message.receive_v1",
            {
                "sender": {
                    "sender_id": {"open_id": "ou_sender"},
                    "sender_type": "user",
                    "tenant_key": "tenant",
                },
                "message": {
                    "message_id": "om_message",
                    "chat_id": "oc_chat",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": '{"text":"你好"}',
                },
            },
        )
    )

    assert isinstance(data, LarkMessageReceiveData)
    assert data.event_type is LarkType.MESSAGE_RECEIVE
    assert data.sender.sender_id.open_id == "ou_sender"
    assert data.message.text == "你好"
    assert data.raw_data["schema"] == "2.0"


@pytest.mark.parametrize(
    ("event_type", "event", "expected_class", "expected_status"),
    [
        (
            "im.chat.member.user.added_v1",
            {
                "chat_id": "oc_chat",
                "users": [
                    {
                        "name": "测试用户",
                        "tenant_key": "tenant",
                        "user_id": {"open_id": "ou_user"},
                    }
                ],
            },
            LarkUserAddedData,
            LarkType.USER_ADDED,
        ),
        (
            "application.bot.menu_v6",
            {
                "operator": {
                    "operator_name": "测试用户",
                    "operator_id": {"open_id": "ou_user"},
                },
                "event_key": "help",
                "timestamp": 1720000000,
            },
            LarkMenuData,
            LarkType.MENU,
        ),
    ],
)
def test_common_events_are_typed(
    event_type: str,
    event: dict,
    expected_class: type,
    expected_status: LarkType,
) -> None:
    data = LarkData.from_envelope(_envelope(event_type, event))

    assert isinstance(data, expected_class)
    assert data.event_type is expected_status


def test_custom_event_falls_back_to_unknown_without_losing_payload() -> None:
    data = LarkData.from_envelope(
        _envelope("contact.user.created_v3", {"user": {"open_id": "ou_user"}})
    )

    assert isinstance(data, LarkUnknownData)
    assert data.event_type is LarkType.UNKNOWN
    assert data.event_type_name == "contact.user.created_v3"
    assert data.raw_data["event"]["user"]["open_id"] == "ou_user"


def test_invalid_envelope_is_rejected() -> None:
    with pytest.raises(ValueError, match="header 或 event"):
        LarkData.from_envelope({"schema": "2.0"})
