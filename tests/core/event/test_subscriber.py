"""Tests for Subscriber and SubscriberGroup."""

from uuid import UUID

from bilipy_bot.core.event.subscriber import Subscriber, SubscriberGroup
from bilipy_bot.core.types import BaseType


class StubType(BaseType):
    ALL = "stub.all"
    EVENT = "stub.event"


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
    """Test SubscriberGroup add/get/query."""

    def test_uids_empty_initially(self):
        """新建的 SubscriberGroup uid 列表应为空."""
        group = SubscriberGroup()
        assert group.uids == []

    def test_add_new_uuid(self):
        """向新 UUID 添加订阅者应创建新列表."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        group.add(
            uuid, Subscriber(callback=_async_callback, status_filter=StubType.EVENT)
        )
        assert len(group.uids) == 1
        assert uuid in group.uids

    def test_add_existing_uuid_appends(self):
        """向已存在的 UUID 添加应追加到已有列表."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        group.add(
            uuid, Subscriber(callback=_async_callback, status_filter=StubType.EVENT)
        )
        group.add(
            uuid, Subscriber(callback=_async_callback, status_filter=StubType.ALL)
        )
        assert len(group.get_subscriber(uuid)) == 2

    def test_get_subscriber_exists(self):
        """get_subscriber 应返回正确的订阅者列表."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        sub = Subscriber(callback=_async_callback, status_filter=StubType.EVENT)
        group.add(uuid, sub)
        result = group.get_subscriber(uuid)
        assert result == [sub]

    def test_get_subscriber_missing(self):
        """get_subscriber 不存在的 UUID 应返回空列表."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        assert group.get_subscriber(uuid) == []

    def test_uids_returns_all(self):
        """uids 属性应返回所有已注册的 UUID."""
        group = SubscriberGroup()
        u1 = UUID("00000000-0000-0000-0000-000000000001")
        u2 = UUID("00000000-0000-0000-0000-000000000002")
        group.add(
            u1, Subscriber(callback=_async_callback, status_filter=StubType.EVENT)
        )
        group.add(
            u2, Subscriber(callback=_async_callback, status_filter=StubType.EVENT)
        )
        assert set(group.uids) == {u1, u2}
