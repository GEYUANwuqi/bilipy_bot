"""Tests for Subscriber and SubscriberGroup (compiled dispatch)."""

from uuid import UUID

import pytest

from butter_bot.core.event.subscriber import Subscriber, SubscriberGroup
from butter_bot.core.exceptions import SubscriptionError
from butter_bot.core.types import BaseType


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


class TestSubscriberGroupNoMatch:
    """无匹配的订阅规则必须报错，不能静默丢弃（ERR-001）."""

    def test_no_match_raises_subscription_error(self):
        """规则在 supported_types 中无匹配时应抛 SubscriptionError."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        sub = Subscriber(callback=_async_callback, status_filter=r"typo\.value")

        with pytest.raises(SubscriptionError):
            group.add(uuid, sub, StubType)

    def test_no_match_error_lists_available_statuses(self):
        """报错信息应给出可用状态值，便于定位拼写错误."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        sub = Subscriber(callback=_async_callback, status_filter=r"stub\.evnet")

        with pytest.raises(SubscriptionError, match="stub.event"):
            group.add(uuid, sub, StubType)

    def test_no_match_does_not_register(self):
        """报错的订阅不应留下任何派发表痕迹."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        sub = Subscriber(callback=_async_callback, status_filter=r"nope\..*")

        with pytest.raises(SubscriptionError):
            group.add(uuid, sub, StubType)

        assert group.uids == []


class TestSubscriberGroupRemove:
    """remove 应清掉某 uuid 的全部订阅（ARCH-001）."""

    def test_remove_returns_callback_count(self):
        """remove 应返回被移除的回调数量."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        group.add(
            uuid,
            Subscriber(callback=_async_callback, status_filter=StubType.EVENT),
            StubType,
        )
        group.add(
            uuid,
            Subscriber(callback=_async_callback, status_filter=StubType.INACTIVE),
            StubType,
        )
        assert group.remove(uuid) == 2

    def test_remove_clears_dispatch_table(self):
        """remove 后 get_callbacks 应返回空."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000001")
        group.add(
            uuid,
            Subscriber(callback=_async_callback, status_filter=StubType.ALL),
            StubType,
        )
        group.remove(uuid)
        assert group.get_callbacks(uuid, StubType.EVENT) == ()
        assert uuid not in group.uids

    def test_remove_unknown_uuid_returns_zero(self):
        """移除未注册的 uuid 应返回 0."""
        group = SubscriberGroup()
        uuid = UUID("00000000-0000-0000-0000-000000000009")
        assert group.remove(uuid) == 0

    def test_remove_does_not_affect_other_uuid(self):
        """移除一个 uuid 不应影响另一个 uuid 的订阅."""
        group = SubscriberGroup()
        u1 = UUID("00000000-0000-0000-0000-000000000001")
        u2 = UUID("00000000-0000-0000-0000-000000000002")
        for uid in (u1, u2):
            group.add(
                uid,
                Subscriber(callback=_async_callback, status_filter=StubType.EVENT),
                StubType,
            )
        group.remove(u1)
        assert len(group.get_callbacks(u2, StubType.EVENT)) == 1
