"""Tests for EventBus publish/subscribe flow with compiled dispatch."""

import asyncio
import inspect
from uuid import UUID

import pytest

from butterbot.core.data import BaseDataMixin
from butterbot.core.event import Event, EventBus
from butterbot.core.filter import BaseFilter
from butterbot.core.types import BaseType


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
        """add_subscriber 后订阅者应被注册到派发表."""
        bus = EventBus()

        async def cb(event): ...

        bus.add_subscriber(fixed_uuid, cb, BusType.EVENT_A, supported_types=BusType)
        callbacks = bus._subscriber_group.get_callbacks(fixed_uuid, BusType.EVENT_A)
        assert len(callbacks) == 1

    def test_wrap_callback_accepts_async(self):
        """_wrap_callback 应接受 async 函数并返回可调用对象."""
        bus = EventBus()

        async def good():
            pass

        wrapped = bus._wrap_callback(good)
        assert inspect.iscoroutinefunction(wrapped)

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

        @bus.subscribe(fixed_uuid, BusType.EVENT_A, supported_types=BusType)
        async def handler(event): ...

        callbacks = bus._subscriber_group.get_callbacks(fixed_uuid, BusType.EVENT_A)
        assert any(cb.__name__ == "handler" for cb in callbacks)

    @pytest.mark.asyncio
    async def test_publish_matching_status(self, fixed_uuid: UUID):
        """publish 匹配状态时应触发回调."""
        bus = EventBus()
        received = asyncio.Queue()

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(fixed_uuid, cb, BusType.EVENT_A, supported_types=BusType)
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

        bus.add_subscriber(fixed_uuid, cb, BusType.EVENT_A, supported_types=BusType)
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

        bus.add_subscriber(fixed_uuid, cb1, BusType.ALL, supported_types=BusType)
        bus.add_subscriber(fixed_uuid, cb2, BusType.EVENT_A, supported_types=BusType)
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

        bus.add_subscriber(fixed_uuid, cb, BusType.EVENT_A, supported_types=BusType)
        data = MockData()
        data.value = "hello"
        event = Event(data=data, status=BusType.EVENT_A)
        await bus.publish(fixed_uuid, event)

        await asyncio.sleep(0)
        result = received.get_nowait()
        assert result.data.value == "hello"
        assert result.status == BusType.EVENT_A

    # ============ str 和 re.Pattern 正则订阅（编译展开）============

    @pytest.mark.asyncio
    async def test_publish_str_regex_matching(self, fixed_uuid: UUID):
        """str 正则订阅，匹配时应触发回调."""
        bus = EventBus()
        received = asyncio.Queue()

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(fixed_uuid, cb, r"bus\.event_a", supported_types=BusType)
        event = Event(data=MockData(), status=BusType.EVENT_A)
        await bus.publish(fixed_uuid, event)

        await asyncio.sleep(0)
        assert not received.empty()

    @pytest.mark.asyncio
    async def test_publish_str_regex_non_matching(self, fixed_uuid: UUID):
        """str 正则为 status_filter，不匹配时不触发回调."""
        bus = EventBus()
        received = asyncio.Queue()

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(fixed_uuid, cb, r"bus\.event_a", supported_types=BusType)
        event = Event(data=MockData(), status=BusType.EVENT_B)
        await bus.publish(fixed_uuid, event)

        await asyncio.sleep(0)
        assert received.empty()

    @pytest.mark.asyncio
    async def test_publish_str_regex_wildcard(self, fixed_uuid: UUID):
        """str 正则 ``.*`` 通配应匹配多个状态."""
        bus = EventBus()
        received = asyncio.Queue()

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(fixed_uuid, cb, r"bus\..*", supported_types=BusType)
        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))
        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_B))

        await asyncio.sleep(0)
        assert received.qsize() == 2

    @pytest.mark.asyncio
    async def test_publish_pattern_matching(self, fixed_uuid: UUID):
        """编译好的 re.Pattern 订阅，匹配时应触发回调."""
        import re

        bus = EventBus()
        received = asyncio.Queue()
        pattern = re.compile(r"bus\.event_a")

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(fixed_uuid, cb, pattern, supported_types=BusType)
        event = Event(data=MockData(), status=BusType.EVENT_A)
        await bus.publish(fixed_uuid, event)

        await asyncio.sleep(0)
        assert not received.empty()

    @pytest.mark.asyncio
    async def test_publish_pattern_non_matching(self, fixed_uuid: UUID):
        """编译好的 re.Pattern，不匹配时不触发回调."""
        import re

        bus = EventBus()
        received = asyncio.Queue()
        pattern = re.compile(r"bus\.event_a")

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(fixed_uuid, cb, pattern, supported_types=BusType)
        event = Event(data=MockData(), status=BusType.EVENT_B)
        await bus.publish(fixed_uuid, event)

        await asyncio.sleep(0)
        assert received.empty()

    @pytest.mark.asyncio
    async def test_publish_pattern_wildcard(self, fixed_uuid: UUID):
        """编译好的 Pattern ``.*`` 通配应匹配多个状态."""
        import re

        bus = EventBus()
        received = asyncio.Queue()
        pattern = re.compile(r"bus\..*")

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(fixed_uuid, cb, pattern, supported_types=BusType)
        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))
        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_B))

        await asyncio.sleep(0)
        assert received.qsize() == 2

    @pytest.mark.asyncio
    async def test_publish_str_regex_with_enum_mixed(self, fixed_uuid: UUID):
        """同一事件源同时存在 str 正则和枚举订阅者，两者独立编译展开."""
        bus = EventBus()
        str_received = asyncio.Queue()
        enum_received = asyncio.Queue()

        async def cb_str(event):
            await str_received.put(event)

        async def cb_enum(event):
            await enum_received.put(event)

        bus.add_subscriber(fixed_uuid, cb_str, r"bus\.event_a", supported_types=BusType)
        bus.add_subscriber(
            fixed_uuid, cb_enum, BusType.EVENT_B, supported_types=BusType
        )

        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))

        await asyncio.sleep(0)
        assert not str_received.empty()
        assert enum_received.empty()

    @pytest.mark.asyncio
    async def test_publish_pattern_with_enum_mixed(self, fixed_uuid: UUID):
        """同一事件源同时存在 re.Pattern 和枚举订阅者，两者独立编译展开."""
        import re

        bus = EventBus()
        pattern_received = asyncio.Queue()
        enum_received = asyncio.Queue()
        pattern = re.compile(r"bus\.event_a")

        async def cb_pattern(event):
            await pattern_received.put(event)

        async def cb_enum(event):
            await enum_received.put(event)

        bus.add_subscriber(fixed_uuid, cb_pattern, pattern, supported_types=BusType)
        bus.add_subscriber(
            fixed_uuid, cb_enum, BusType.EVENT_B, supported_types=BusType
        )

        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))

        await asyncio.sleep(0)
        assert not pattern_received.empty()
        assert enum_received.empty()

    # ============ 防止 Task 被 GC（commit 9acbdb3）============

    @pytest.mark.asyncio
    async def test_background_task_tracked_and_cleaned(self, fixed_uuid: UUID):
        """publish 后回调 task 被 _background_tasks 跟踪，完成后自动移除."""
        bus = EventBus()
        started = asyncio.Event()
        can_finish = asyncio.Event()

        async def cb(event):
            started.set()
            await can_finish.wait()

        bus.add_subscriber(fixed_uuid, cb, BusType.EVENT_A, supported_types=BusType)
        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))
        await started.wait()

        # task 尚未完成，应被强引用
        assert len(bus._background_tasks) == 1

        # 让回调完成
        can_finish.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # task 已完成，应从 _background_tasks 移除
        assert len(bus._background_tasks) == 0

    @pytest.mark.asyncio
    async def test_multiple_publish_tracks_separate_tasks(self, fixed_uuid: UUID):
        """多次 publish 应各自独立跟踪 task."""
        bus = EventBus()
        can_finish = asyncio.Event()

        async def cb(event):
            await can_finish.wait()

        bus.add_subscriber(fixed_uuid, cb, BusType.EVENT_A, supported_types=BusType)

        # 连续发布两个事件
        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))
        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))

        # 两个 task 都应在 _background_tasks 中
        assert len(bus._background_tasks) == 2

        can_finish.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert len(bus._background_tasks) == 0


# ============ 过滤器相关测试 ============


class _PassFilter(BaseFilter):
    """始终返回 True 的过滤器。"""

    def __init__(self, label: str = "") -> None:
        self.filters = [self]
        self._label = label

    def check(self, event: Event) -> bool:
        return True


class _BlockFilter(BaseFilter):
    """始终返回 False 的过滤器。"""

    def __init__(self, label: str = "") -> None:
        self.filters = [self]
        self._label = label

    def check(self, event: Event) -> bool:
        return False


class TestEventBusWithFilter:
    """Test EventBus event_filter integration."""

    @pytest.mark.asyncio
    async def test_publish_with_filter_passing(self, fixed_uuid: UUID):
        """event_filter.check() 返回 True 时应触发回调."""
        bus = EventBus()
        received = asyncio.Queue()

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(
            fixed_uuid,
            cb,
            BusType.EVENT_A,
            supported_types=BusType,
            event_filter=_PassFilter(),
        )
        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))
        await asyncio.sleep(0)
        assert not received.empty()

    @pytest.mark.asyncio
    async def test_publish_with_filter_blocking(self, fixed_uuid: UUID):
        """event_filter.check() 返回 False 时应阻止回调."""
        bus = EventBus()
        received = asyncio.Queue()

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(
            fixed_uuid,
            cb,
            BusType.EVENT_A,
            supported_types=BusType,
            event_filter=_BlockFilter(),
        )
        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))
        await asyncio.sleep(0)
        assert received.empty()

    @pytest.mark.asyncio
    async def test_publish_with_and_filter_short_circuit(self, fixed_uuid: UUID):
        """AndFilter: 第一个 filter 返回 False 时不再检查后续."""
        call_count = 0

        class TrackingFilter(BaseFilter):
            def __init__(self, returns: bool):
                self.filters = [self]
                self._returns = returns

            def check(self, event: Event) -> bool:
                nonlocal call_count
                call_count += 1
                return self._returns

        bus = EventBus()
        received = asyncio.Queue()

        async def cb(event):
            await received.put(event)

        # AndFilter: 第一个返回 False → 短路，第二个不应被调用
        and_filter = TrackingFilter(False) & TrackingFilter(True)
        bus.add_subscriber(
            fixed_uuid,
            cb,
            BusType.EVENT_A,
            supported_types=BusType,
            event_filter=and_filter,
        )
        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))
        await asyncio.sleep(0)

        assert received.empty()
        assert call_count == 1  # 仅第一个 filter 被调用

    @pytest.mark.asyncio
    async def test_publish_with_or_filter_short_circuit(self, fixed_uuid: UUID):
        """OrFilter: 第一个 filter 返回 True 时不再检查后续."""
        call_count = 0

        class TrackingFilter(BaseFilter):
            def __init__(self, returns: bool):
                self.filters = [self]
                self._returns = returns

            def check(self, event: Event) -> bool:
                nonlocal call_count
                call_count += 1
                return self._returns

        bus = EventBus()
        received = asyncio.Queue()

        async def cb(event):
            await received.put(event)

        # OrFilter: 第一个返回 True → 短路，第二个不应被调用
        or_filter = TrackingFilter(True) | TrackingFilter(False)
        bus.add_subscriber(
            fixed_uuid,
            cb,
            BusType.EVENT_A,
            supported_types=BusType,
            event_filter=or_filter,
        )
        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))
        await asyncio.sleep(0)

        assert not received.empty()
        assert call_count == 1  # 仅第一个 filter 被调用

    @pytest.mark.asyncio
    async def test_publish_no_filter_unchanged(self, fixed_uuid: UUID):
        """不提供 event_filter 时，行为应与改动前完全一致."""
        bus = EventBus()
        received = asyncio.Queue()

        async def cb(event):
            await received.put(event)

        bus.add_subscriber(fixed_uuid, cb, BusType.EVENT_A, supported_types=BusType)

        # 回调是裸回调，而非 filtered_wrapper
        callbacks = bus._subscriber_group.get_callbacks(fixed_uuid, BusType.EVENT_A)
        assert len(callbacks) == 1
        cb_name = getattr(callbacks[0], "__name__", "<lambda>")
        assert cb_name == "cb"  # 保留原始函数名

        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))
        await asyncio.sleep(0)
        assert not received.empty()

    @pytest.mark.asyncio
    async def test_subscribe_decorator_with_filter(self, fixed_uuid: UUID):
        """subscribe 装饰器的 event_filter 应正确传递并生效."""
        bus = EventBus()
        received = asyncio.Queue()

        @bus.subscribe(
            fixed_uuid,
            BusType.EVENT_A,
            supported_types=BusType,
            event_filter=_BlockFilter(),
        )
        async def handler(event):
            await received.put(event)

        await bus.publish(fixed_uuid, Event(data=MockData(), status=BusType.EVENT_A))
        await asyncio.sleep(0)
        assert received.empty()

    @pytest.mark.asyncio
    async def test_wraps_preserves_name(self, fixed_uuid: UUID):
        """包装后的回调应保留原始函数名."""
        bus = EventBus()

        async def my_handler(event):
            pass

        bus.add_subscriber(
            fixed_uuid,
            my_handler,
            BusType.EVENT_A,
            supported_types=BusType,
            event_filter=_PassFilter(),
        )
        callbacks = bus._subscriber_group.get_callbacks(fixed_uuid, BusType.EVENT_A)
        assert len(callbacks) == 1
        assert callbacks[0].__name__ == "my_handler"


class TestEventBusCapacity:
    """可选容量应限制 in-flight task，并对发布者施加背压."""

    def test_invalid_capacity_raises(self):
        """容量必须是正整数或 None."""
        for value in (0, -1, True):
            with pytest.raises(ValueError, match="max_pending_callbacks"):
                EventBus(max_pending_callbacks=value)

    @pytest.mark.asyncio
    async def test_capacity_backpressures_publish(self, fixed_uuid: UUID):
        """容量耗尽时后续 publish 应等待，而不是继续创建 task."""
        bus = EventBus(max_pending_callbacks=1)
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        release_first = asyncio.Event()
        active = 0
        max_active = 0
        calls = 0

        async def callback(event):
            nonlocal active, calls, max_active
            calls += 1
            active += 1
            max_active = max(max_active, active)
            try:
                if calls == 1:
                    first_started.set()
                    await release_first.wait()
                else:
                    second_started.set()
            finally:
                active -= 1

        bus.add_subscriber(
            fixed_uuid,
            callback,
            BusType.EVENT_A,
            supported_types=BusType,
        )

        event = Event(data=MockData(), status=BusType.EVENT_A)
        await bus.publish(fixed_uuid, event)
        await first_started.wait()

        second_publish = asyncio.create_task(bus.publish(fixed_uuid, event))
        await asyncio.sleep(0)

        assert not second_publish.done()
        assert bus.pending_callbacks == 1

        release_first.set()
        await second_publish
        await second_started.wait()
        await bus.close()

        assert max_active == 1
        assert bus.pending_callbacks == 0

    @pytest.mark.asyncio
    async def test_close_drops_publish_waiting_for_capacity(self, fixed_uuid: UUID):
        """关闭时等待容量的 publish 不应在获得容量后创建新回调."""
        bus = EventBus(max_pending_callbacks=1)
        started = asyncio.Event()
        calls = 0

        async def callback(event):
            nonlocal calls
            calls += 1
            started.set()
            await asyncio.Event().wait()

        bus.add_subscriber(
            fixed_uuid,
            callback,
            BusType.EVENT_A,
            supported_types=BusType,
        )

        event = Event(data=MockData(), status=BusType.EVENT_A)
        await bus.publish(fixed_uuid, event)
        await started.wait()
        waiting_publish = asyncio.create_task(bus.publish(fixed_uuid, event))
        await asyncio.sleep(0)

        await bus.close(timeout=0.01)
        await waiting_publish

        assert calls == 1
        assert bus.pending_callbacks == 0


class TestEventBusOwnership:
    """扩展所有权只影响定向撤销，不改变现有派发语义."""

    @pytest.mark.asyncio
    async def test_remove_and_drain_owner_keeps_other_owner(
        self,
        fixed_uuid: UUID,
    ):
        bus = EventBus()
        owner_a_started = asyncio.Event()
        owner_b_started = asyncio.Event()
        owner_a_cancelled = asyncio.Event()
        release_owner_b = asyncio.Event()

        async def owner_a_callback(event):
            owner_a_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                owner_a_cancelled.set()
                raise

        async def owner_b_callback(event):
            owner_b_started.set()
            await release_owner_b.wait()

        bus.add_subscriber(
            fixed_uuid,
            owner_a_callback,
            BusType.EVENT_A,
            supported_types=BusType,
            owner_id="extension-a",
        )
        bus.add_subscriber(
            fixed_uuid,
            owner_b_callback,
            BusType.EVENT_A,
            supported_types=BusType,
            owner_id="extension-b",
        )

        event = Event(data=MockData(), status=BusType.EVENT_A)
        await bus.publish(fixed_uuid, event)
        await owner_a_started.wait()
        await owner_b_started.wait()

        assert bus.remove_subscribers_by_owner("extension-a") == 1
        assert await bus.drain_owner("extension-a", timeout=0) == 1
        assert owner_a_cancelled.is_set()
        assert bus.pending_callbacks_for("extension-a") == 0
        assert bus.pending_callbacks_for("extension-b") == 1

        release_owner_b.set()
        assert await bus.drain_owner("extension-b") == 1
        assert bus.pending_callbacks == 0
