"""Tests for Subscriber and SubscriberGroup (compiled dispatch)."""

from uuid import UUID

import pytest

from bilipy_bot.core.event.subscriber import Subscriber, SubscriberGroup
from bilipy_bot.core.types import BaseType


class StubType(BaseType):
    ALL = "stub.all"
    EVENT = "stub.event"
    INACTIVE = "stub.inactive"


async def _async_callback(event) -> None:
    """A minimal async callback for testing."""
    pass


class TestSubscriber:
    """Test Subscriber dataclass."""

    def test_construction(self):
        """Subscriber 应正确存储 callback 和 status_filter."""
        sub = Subscriber(callback=_async_callback, status_filter=StubType.EVENT)
        assert sub.callback is _async_callback
        assert sub.status_filter == StubType.EVENT


class TestSubscriberGroup:
    """Test SubscriberGroup compiled dispatch."""

    def test_uids_empty_initially(self):
        """新建的 SubscriberGroup uid 列表应为空."""
        group = SubscriberGroup()
        assert group.uids == []

    def test_add_without_supported_types_raises(self):
        """未提供 supported_types 时应抛出 TypeError."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        sub = Subscriber(callback=_async_callback, status_filter=StubType.EVENT)
        with pytest.raises(TypeError):
            group.add(uuid, sub, supported_types=None)

    def test_add_new_uuid(self):
        """向新 UUID 添加订阅者应创建新条目."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        sub = Subscriber(callback=_async_callback, status_filter=StubType.EVENT)
        group.add(uuid, sub, StubType)
        assert len(group.uids) == 1
        assert uuid in group.uids

    def test_multiple_subscribers_same_uuid(self):
        """同一 uuid 多个订阅者应各自展开到对应的状态桶."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")

        sub1 = Subscriber(callback=_async_callback, status_filter=StubType.EVENT)
        sub2 = Subscriber(callback=_async_callback, status_filter=StubType.INACTIVE)

        group.add(uuid, sub1, StubType)
        group.add(uuid, sub2, StubType)

        assert len(group.get_callbacks(uuid, StubType.EVENT)) == 1
        assert len(group.get_callbacks(uuid, StubType.INACTIVE)) == 1

    def test_all_rule_expands(self):
        """ALL 规则应展开到所有具体状态."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        sub = Subscriber(callback=_async_callback, status_filter=StubType.ALL)
        group.add(uuid, sub, StubType)

        assert len(group.get_callbacks(uuid, StubType.EVENT)) == 1
        assert len(group.get_callbacks(uuid, StubType.INACTIVE)) == 1

    def test_get_callbacks_missing_uuid(self):
        """不存在的 UUID 应返回空列表."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        assert group.get_callbacks(uuid, StubType.EVENT) == ()

    def test_get_callbacks_unknown_status(self):
        """存在的 UUID 但未知状态应返回空列表."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        sub = Subscriber(callback=_async_callback, status_filter=StubType.EVENT)
        group.add(uuid, sub, StubType)
        assert group.get_callbacks(uuid, StubType.INACTIVE) == ()

    def test_uids_returns_all(self):
        """uids 属性应返回所有已注册的 UUID."""
        group = SubscriberGroup()
        u1 = UUID("00000000-0000-0000-0000-000000000001")
        u2 = UUID("00000000-0000-0000-0000-000000000002")
        group.add(
            u1,
            Subscriber(callback=_async_callback, status_filter=StubType.EVENT),
            StubType,
        )
        group.add(
            u2,
            Subscriber(callback=_async_callback, status_filter=StubType.EVENT),
            StubType,
        )
        assert set(group.uids) == {u1, u2}
