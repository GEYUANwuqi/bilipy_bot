"""NapcatSource 分发集成测试."""

from uuid import uuid4

import pytest

from butterbot.app import RuntimeConfig
from butterbot.core.context import AppContext
from butterbot.core.source import SourceHealthState
from butterbot.sources.napcat.data import NapcatGroupMessageData
from butterbot.sources.napcat.source import NapcatSource
from butterbot.sources.napcat.types import NapcatType
from butterbot.utils import ConnectionHealth, ConnectionHealthState


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

    def test_connection_health_is_exposed_by_source(self) -> None:
        source = NapcatSource()
        source.running = True

        source._handle_connection_health(
            ConnectionHealth(
                state=ConnectionHealthState.READY,
                last_success_at=123.0,
                last_error_at=None,
                last_error_type=None,
                last_error_message=None,
            )
        )
        assert source.health.state is SourceHealthState.READY
        assert source.health.last_success_at == 123.0

        source._handle_connection_health(
            ConnectionHealth(
                state=ConnectionHealthState.DEGRADED,
                last_success_at=123.0,
                last_error_at=124.0,
                last_error_type="ConnectionError",
                last_error_message="connection lost",
            )
        )
        assert source.health.state is SourceHealthState.DEGRADED
        assert source.health.last_error_type == "ConnectionError"
        assert source.health.last_error_message == "connection lost"
