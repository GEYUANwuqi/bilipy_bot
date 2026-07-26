"""NapcatSource dispatch integration tests."""

from uuid import uuid4

import pytest

from bilipy_bot.app import RuntimeConfig
from bilipy_bot.core.context import AppContext
from bilipy_bot.sources.napcat.data import NapcatGroupMessageData
from bilipy_bot.sources.napcat.source import NapcatSource
from bilipy_bot.sources.napcat.types import NapcatType


def _group_message() -> dict[str, object]:
    return {
        "time": 1,
        "self_id": 10000,
        "post_type": "message",
        "message_type": "group",
        "sub_type": "normal",
        "message_id": 123,
        "user_id": 456,
        "message": [{"type": "text", "data": {"text": "hello"}}],
        "raw_message": "hello",
        "font": 0,
        "group_id": 789,
        "sender": {"user_id": 456, "nickname": "tester"},
    }


class TestNapcatSourceDispatch:
    @pytest.mark.asyncio
    async def test_status_comes_from_dispatched_data(self) -> None:
        """事件状态应来自完成 discriminator 分发后的 Data 类型."""
        source = NapcatSource(uuid=uuid4())
        ctx = AppContext(RuntimeConfig())
        source.bind(ctx)
        received = []

        async def callback(event) -> None:
            received.append(event)

        ctx.bus.add_subscriber(
            source.uuid,
            callback,
            NapcatType.GROUP_MESSAGE,
            NapcatType,
        )

        await source._process_messages(_group_message())
        await ctx.bus.close()

        assert len(received) == 1
        assert received[0].status is NapcatType.GROUP_MESSAGE
        assert isinstance(received[0].data, NapcatGroupMessageData)
