"""Tests for EventBus publish/subscribe flow."""

import asyncio
from uuid import UUID

import pytest

from bilipy_bot.core.data import BaseDataMixin
from bilipy_bot.core.event import Event, EventBus
from bilipy_bot.core.types import BaseType


class BusType(BaseType):
    ALL = "bus.all"
    EVENT_A = "bus.event_a"
    EVENT_B = "bus.event_b"


class MockData(BaseDataMixin):
    """Minimal data payload for events."""

    value: str = ""


class TestEventBus:
    """Test EventBus subscription and publishing."""

    def test_add_subscriber_registers(self, fixed_uuid: UUID):
        """add_subscriber 后订阅者应被注册."""
        bus = EventBus()

        async def cb(event): ...

        bus.add_subscriber(fixed_uuid, cb, BusType.EVENT_A)
        group = bus._subscriber_group
        subs = group.get_subscriber(fixed_uuid)
        assert len(subs) == 1
        assert subs[0].callback.__name__ == cb.__name__

    def test_wrap_callback_accepts_async(self):
        """_wrap_callback 应接受 async 函数并返回可调用对象."""
        bus = EventBus()

        async def good():
            pass

        wrapped = bus._wrap_callback(good)
        assert asyncio.iscoroutinefunction(wrapped)

    def test_wrap_callback_rejects_sync(self):
        """_wrap_callback 应拒绝同步函数并抛出 TypeError."""
        bus = EventBus()

        def bad():
            pass

        with pytest.raises(TypeError):
            bus._wrap_callback(bad)

    def test_subscribe_decorator(self, fixed_uuid: UUID):
        """subscribe 装饰器应注册订阅者并返回原函数."""
        bus = EventBus()

        @bus.subscribe(fixed_uuid, BusType.EVENT_A)
        async def handler(event): ...

        subs = bus._subscriber_group.get_subscriber(fixed_uuid)
        assert any(s.callback.__name__ == "handler" for s in subs)

    @pytest.mark.asyncio
    async def test_publish_matching_status(self, fixed_uuid: UUID):
        """publish 匹配状态时应触发回调."""
        bus = EventBus()
        received = asyncio.Queue()

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(fixed_uuid, cb, BusType.EVENT_A)
        event = Event(data=MockData(), status=BusType.EVENT_A)
        await bus.publish(fixed_uuid, event)

        await asyncio.sleep(0)
        assert not received.empty()

    @pytest.mark.asyncio
    async def test_publish_non_matching_status(self, fixed_uuid: UUID):
        """publish 不匹配状态时不应触发回调."""
        bus = EventBus()
        received = asyncio.Queue()

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(fixed_uuid, cb, BusType.EVENT_A)
        event = Event(data=MockData(), status=BusType.EVENT_B)
        await bus.publish(fixed_uuid, event)

        await asyncio.sleep(0)
        assert received.empty()

    @pytest.mark.asyncio
    async def test_publish_no_subscribers(self, fixed_uuid: UUID):
        """publish 无订阅者的 UUID 不应抛出异常."""
        bus = EventBus()
        event = Event(data=MockData(), status=BusType.EVENT_A)
        await bus.publish(fixed_uuid, event)

    @pytest.mark.asyncio
    async def test_publish_multiple_subscribers(self, fixed_uuid: UUID):
        """所有匹配的订阅者都应被触发."""
        bus = EventBus()
        count = 0

        async def cb1(event):
            nonlocal count
            count += 1

        async def cb2(event):
            nonlocal count
            count += 1

        bus.add_subscriber(fixed_uuid, cb1, BusType.ALL)
        bus.add_subscriber(fixed_uuid, cb2, BusType.EVENT_A)
        event = Event(data=MockData(), status=BusType.EVENT_A)
        await bus.publish(fixed_uuid, event)

        await asyncio.sleep(0)
        assert count == 2

    @pytest.mark.asyncio
    async def test_publish_callback_receives_correct_event(self, fixed_uuid: UUID):
        """回调接收到的 Event 应与发布的一致."""
        bus = EventBus()
        received = asyncio.Queue()

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(fixed_uuid, cb, BusType.EVENT_A)
        data = MockData()
        data.value = "hello"
        event = Event(data=data, status=BusType.EVENT_A)
        await bus.publish(fixed_uuid, event)

        await asyncio.sleep(0)
        result = received.get_nowait()
        assert result.data.value == "hello"
        assert result.status == BusType.EVENT_A
