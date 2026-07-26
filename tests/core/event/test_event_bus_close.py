"""Tests for EventBus shutdown: drain, timeout-cancel, unsubscribe (ASYNC-001)."""

import asyncio
from uuid import UUID

import pytest

from butter_bot.core.data import BaseDataMixin
from butter_bot.core.event import Event, EventBus
from butter_bot.core.types import BaseType


class BusType(BaseType):
    ALL = "bus.all"
    EVENT = "bus.event"


class MockData(BaseDataMixin):
    def __init__(self, value: str = "") -> None:
        self.value = value


def _event() -> Event:
    return Event(data=MockData("payload"), status=BusType.EVENT)


class TestEventBusCloseDrain:
    """close 应等待 in-flight 回调真正跑完，而不是让它们被 GC 掉."""

    @pytest.mark.asyncio
    async def test_close_waits_for_slow_callback(self, fixed_uuid: UUID):
        """慢回调应在 close 返回前执行完毕."""
        bus = EventBus()
        finished: list[str] = []

        async def slow_callback(event: Event) -> None:
            await asyncio.sleep(0.05)
            finished.append("done")

        bus.add_subscriber(fixed_uuid, slow_callback, BusType.EVENT, BusType)
        await bus.publish(fixed_uuid, _event())

        assert finished == []  # 尚未完成
        await bus.close(timeout=2.0)
        assert finished == ["done"]

    @pytest.mark.asyncio
    async def test_close_leaves_no_pending_tasks(self, fixed_uuid: UUID):
        """close 之后不应残留未完成的回调任务."""
        bus = EventBus()

        async def slow_callback(event: Event) -> None:
            await asyncio.sleep(0.05)

        bus.add_subscriber(fixed_uuid, slow_callback, BusType.EVENT, BusType)
        await bus.publish(fixed_uuid, _event())
        assert bus.pending_callbacks == 1

        await bus.close(timeout=2.0)
        assert bus.pending_callbacks == 0
        assert bus._background_tasks == set()

    @pytest.mark.asyncio
    async def test_close_drains_multiple_callbacks(self, fixed_uuid: UUID):
        """多个订阅者的回调都应被等待."""
        bus = EventBus()
        finished: list[int] = []

        async def make_callback(index: int):
            async def callback(event: Event) -> None:
                await asyncio.sleep(0.01 * index)
                finished.append(index)

            callback.__name__ = "callback_%s" % index
            return callback

        for i in range(1, 4):
            bus.add_subscriber(
                fixed_uuid, await make_callback(i), BusType.EVENT, BusType
            )

        await bus.publish(fixed_uuid, _event())
        await bus.close(timeout=2.0)
        assert sorted(finished) == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_close_without_pending_returns_immediately(self):
        """无待完成回调时 close 应直接返回."""
        bus = EventBus()
        await bus.close()
        assert bus.closed

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self):
        """重复 close 不应抛出异常."""
        bus = EventBus()
        await bus.close()
        await bus.close()
        assert bus.closed


class TestEventBusCloseTimeout:
    """超时未完成的回调必须被取消，不能无限等待."""

    @pytest.mark.asyncio
    async def test_close_cancels_hanging_callback(self, fixed_uuid: UUID):
        """超时后挂死的回调应被取消."""
        bus = EventBus()
        started = asyncio.Event()
        cancelled: list[str] = []

        async def hanging_callback(event: Event) -> None:
            started.set()
            try:
                await asyncio.Event().wait()  # 永远不会返回
            except asyncio.CancelledError:
                cancelled.append("cancelled")
                raise

        bus.add_subscriber(fixed_uuid, hanging_callback, BusType.EVENT, BusType)
        await bus.publish(fixed_uuid, _event())
        await started.wait()

        await bus.close(timeout=0.05)

        assert cancelled == ["cancelled"]
        assert bus.pending_callbacks == 0

    @pytest.mark.asyncio
    async def test_close_from_inside_callback_does_not_self_await(
        self, fixed_uuid: UUID
    ):
        """在回调内部调用 close 不应自我等待（否则死锁）."""
        bus = EventBus()
        done = asyncio.Event()

        async def closing_callback(event: Event) -> None:
            await bus.close(timeout=1.0)
            done.set()

        bus.add_subscriber(fixed_uuid, closing_callback, BusType.EVENT, BusType)
        await bus.publish(fixed_uuid, _event())

        await asyncio.wait_for(done.wait(), timeout=2.0)
        assert bus.closed


class TestEventBusPublishAfterClose:
    """关闭后的总线不应再派发事件."""

    @pytest.mark.asyncio
    async def test_publish_after_close_is_dropped(self, fixed_uuid: UUID):
        """close 之后 publish 不应触发回调."""
        bus = EventBus()
        calls: list[str] = []

        async def callback(event: Event) -> None:
            calls.append("called")

        bus.add_subscriber(fixed_uuid, callback, BusType.EVENT, BusType)
        await bus.close()
        await bus.publish(fixed_uuid, _event())
        await asyncio.sleep(0)

        assert calls == []
        assert bus.pending_callbacks == 0

    @pytest.mark.asyncio
    async def test_closed_property_reflects_state(self):
        """closed 属性应正确反映关闭状态."""
        bus = EventBus()
        assert not bus.closed
        await bus.close()
        assert bus.closed


class TestEventBusRemoveSubscribers:
    """事件源被移除时必须能清掉它的订阅（ARCH-001）."""

    @pytest.mark.asyncio
    async def test_remove_subscribers_stops_dispatch(self, fixed_uuid: UUID):
        """退订后 publish 不应再触发回调."""
        bus = EventBus()
        calls: list[str] = []

        async def callback(event: Event) -> None:
            calls.append("called")

        bus.add_subscriber(fixed_uuid, callback, BusType.EVENT, BusType)
        removed = bus.remove_subscribers(fixed_uuid)
        assert removed == 1

        await bus.publish(fixed_uuid, _event())
        await asyncio.sleep(0)
        assert calls == []

    def test_remove_subscribers_counts_all_statuses(self, fixed_uuid: UUID):
        """ALL 规则展开到 N 个状态时应统计 N 个回调."""
        bus = EventBus()

        async def callback(event: Event) -> None:
            pass

        bus.add_subscriber(fixed_uuid, callback, BusType.ALL, BusType)
        # BusType 只有 EVENT 一个具体状态（ALL 是通配符，不计入）
        assert bus.remove_subscribers(fixed_uuid) == 1

    def test_remove_subscribers_unknown_uuid_returns_zero(self, fixed_uuid: UUID):
        """未注册的 uuid 应返回 0 而不是报错."""
        bus = EventBus()
        assert bus.remove_subscribers(fixed_uuid) == 0

    @pytest.mark.asyncio
    async def test_remove_subscribers_does_not_affect_other_sources(
        self, fixed_uuid: UUID, alternate_uuid: UUID
    ):
        """退订一个事件源不应影响其他事件源的订阅."""
        bus = EventBus()
        calls: list[str] = []

        async def callback(event: Event) -> None:
            calls.append("called")

        bus.add_subscriber(fixed_uuid, callback, BusType.EVENT, BusType)
        bus.add_subscriber(alternate_uuid, callback, BusType.EVENT, BusType)

        bus.remove_subscribers(fixed_uuid)
        await bus.publish(alternate_uuid, _event())
        await asyncio.sleep(0)

        assert calls == ["called"]
