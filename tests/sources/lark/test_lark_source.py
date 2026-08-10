from uuid import uuid4

import pytest

from butterbot.app import RuntimeConfig
from butterbot.core.context import AppContext
from butterbot.sources.lark import LarkConfig, LarkSource, LarkType
from butterbot.sources.lark.data import LarkMessageReceiveData


def _message_event(event_id: str = "event-1") -> dict:
    return {
        "schema": "2.0",
        "header": {
            "event_id": event_id,
            "event_type": "im.message.receive_v1",
            "create_time": "1720000000000",
        },
        "event": {
            "sender": {
                "sender_id": {"open_id": "ou_sender"},
                "sender_type": "user",
            },
            "message": {
                "message_id": "om_message",
                "chat_id": "oc_chat",
                "chat_type": "group",
                "message_type": "text",
                "content": '{"text":"hello"}',
            },
        },
    }


@pytest.mark.asyncio
async def test_source_publishes_typed_event_and_deduplicates_event_id() -> None:
    source = LarkSource(uuid=uuid4(), config_key="work")
    ctx = AppContext(
        RuntimeConfig(
            work=LarkConfig(app_id="cli_test", app_secret="secret"),
        )
    )
    source.bind(ctx)
    received = []

    async def callback(event) -> None:
        received.append(event)

    ctx.bus.add_subscriber(
        source.uuid,
        callback,
        LarkType.MESSAGE_RECEIVE,
        LarkType,
    )

    await source._process_event(_message_event())
    await source._process_event(_message_event())
    await ctx.bus.close()

    assert len(received) == 1
    assert received[0].status is LarkType.MESSAGE_RECEIVE
    assert isinstance(received[0].data, LarkMessageReceiveData)
    assert received[0].data.runtime is ctx
    assert received[0].data.config_key == "work"


@pytest.mark.asyncio
async def test_source_can_disable_deduplication() -> None:
    source = LarkSource(config_key="work")
    ctx = AppContext(
        RuntimeConfig(
            work=LarkConfig(
                app_id="cli_test",
                app_secret="secret",
                deduplicate_events=False,
            ),
        )
    )
    source.bind(ctx)
    received = []

    async def callback(event) -> None:
        received.append(event)

    ctx.bus.add_subscriber(source.uuid, callback, LarkType.ALL, LarkType)

    await source._process_event(_message_event())
    await source._process_event(_message_event())
    await ctx.bus.close()

    assert len(received) == 2
