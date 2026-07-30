"""Tests for SourceManager lifecycle management."""

import asyncio
from uuid import UUID

import pytest

from butterbot.app.config import RuntimeConfig
from butterbot.app.source_manager import SourceManager
from butterbot.core.context import AppContext
from butterbot.core.exceptions import LifecycleError, SourceError, SourceStartError
from butterbot.core.source import BaseSource
from butterbot.core.types import BaseType
from butterbot.plugin import SourceRef


class StubType(BaseType):
    ALL = "stub.all"
    EVENT = "stub.event"


class StubSource(BaseSource):
    """Minimal concrete source for testing SourceManager."""

    supported_types = StubType
    source_kind = "stub.events"

    def __init__(self, uuid: UUID | None = None, **kwargs):
        super().__init__(uuid=uuid, **kwargs)
        self.started = False
        self.stopped = False
        self.stop_calls = 0
        self.start_exception: BaseException | None = None
        self.stop_exception: BaseException | None = None

    async def on_start(self):
        if self.start_exception:
            raise self.start_exception
        self.started = True

    async def on_stop(self):
        self.stop_calls += 1
        self.stopped = True
        if self.stop_exception is not None:
            raise self.stop_exception


class OtherSource(BaseSource):
    """A second source type for type-lookup tests."""

    async def on_start(self):
        pass

    async def on_stop(self):
        pass


@pytest.fixture
def manager():
    """Return a fresh SourceManager with an AppContext."""
    config = RuntimeConfig()
    ctx = AppContext(config)
    return SourceManager(ctx)


class TestSourceManager:
    """Test SourceManager add/remove/get/lifecycle."""

    def test_add_source_creates_and_stores(self, manager):
        """add_source 应实例化并存储事件源."""
        source = manager.add_source(StubSource)
        assert isinstance(source, StubSource)
        assert source.uuid in manager.sources

    def test_add_source_returns_instance(self, manager):
        """add_source 应返回创建的事件源实例."""
        source = manager.add_source(StubSource)
        assert isinstance(source, StubSource)

    def test_add_source_rejects_duplicate_uuid(self, manager):
        """显式 UUID 冲突不能覆盖已注册事件源."""
        source = manager.add_source(StubSource)

        with pytest.raises(SourceError, match="UUID.*已注册"):
            manager.add_source(StubSource, uuid=source.uuid)

        assert manager.get_source(source.uuid) is source

    def test_add_source_raises_when_closed(self, manager):
        """close 后添加事件源应抛出 RuntimeError."""
        import asyncio

        asyncio.run(manager.close())
        with pytest.raises(RuntimeError, match="已关闭"):
            manager.add_source(StubSource)

    @pytest.mark.asyncio
    async def test_remove_source_removes_and_returns(self, manager):
        """remove_source 应移除并返回事件源."""
        source = manager.add_source(StubSource)
        removed = await manager.remove_source(source.uuid)
        assert removed is source
        assert source.uuid not in manager.sources

    @pytest.mark.asyncio
    async def test_remove_source_nonexistent_returns_none(self, manager):
        """remove_source 不存在的 UUID 应返回 None."""
        result = await manager.remove_source(
            UUID("00000000-0000-0000-0000-000000000000")
        )
        assert result is None

    def test_get_source_returns_instance(self, manager):
        """get_source 应返回已添加的事件源."""
        source = manager.add_source(StubSource)
        assert manager.get_source(source.uuid) is source

    def test_get_source_by_logical_reference(self, manager):
        """SourceRef 应按 source_kind 和 config_key 解析."""
        manager.add_source(StubSource, config_key="account-a")
        target = manager.add_source(StubSource, config_key="account-b")

        assert manager.get_source(SourceRef("stub.events", "account-b")) is target

    def test_ambiguous_source_reference_raises(self, manager):
        """缺少 config_key 的唯一解析不能偶然返回首个实例."""
        manager.add_source(StubSource, config_key="account-a")
        manager.add_source(StubSource, config_key="account-b")

        with pytest.raises(SourceError, match="匹配到 2 个"):
            manager.get_source(SourceRef("stub.events"))

        assert len(manager.get_sources(SourceRef("stub.events"))) == 2

    def test_plugin_owned_logical_key_rejects_duplicate(self, manager):
        first = manager.add_owned_source(
            "example.one",
            StubSource,
            config_key="account",
        )

        with pytest.raises(SourceError, match="example.one"):
            manager.add_owned_source(
                "example.two",
                StubSource,
                config_key="account",
            )

        assert manager.source_catalog.by_owner("example.one")[0].source_id == first.uuid
        assert manager.source_catalog.by_owner("example.two") == ()

    @pytest.mark.asyncio
    async def test_remove_source_removes_catalog_owner_entry(self, manager):
        source = manager.add_owned_source(
            "example.owner",
            StubSource,
            config_key="account",
        )

        await manager.remove_source(source.uuid)

        assert manager.source_catalog.by_owner("example.owner") == ()

    def test_get_source_nonexistent_returns_none(self, manager):
        """get_source 不存在的 UUID 应返回 None."""
        result = manager.get_source(UUID("00000000-0000-0000-0000-000000000000"))
        assert result is None

    def test_sources_property_returns_copy(self, manager):
        """sources 属性应返回内部 dict 的副本."""
        manager.add_source(StubSource)
        sources_copy = manager.sources
        sources_copy.clear()
        assert len(manager.sources) == 1

    @pytest.mark.asyncio
    async def test_start_sets_running(self, manager):
        """start 后 running 应为 True."""
        await manager.start()
        assert manager.running

    @pytest.mark.asyncio
    async def test_start_binds_context(self, manager):
        """start 后事件源的 _ctx 应被设置."""
        source = manager.add_source(StubSource)
        await manager.start()
        assert source._ctx is manager.ctx

    @pytest.mark.asyncio
    async def test_start_already_running_noop(self, manager):
        """已经 running 时 start 不应抛出异常."""
        await manager.start()
        await manager.start()  # should not raise
        assert manager.running

    @pytest.mark.asyncio
    async def test_stop_sets_not_running(self, manager):
        """stop 后 running 应为 False."""
        await manager.start()
        await manager.stop()
        assert not manager.running

    @pytest.mark.asyncio
    async def test_stop_when_not_running_noop(self, manager):
        """未 running 时 stop 不应抛出异常."""
        await manager.stop()

    @pytest.mark.asyncio
    async def test_close_sets_closed(self, manager):
        """close 后 closed 应为 True."""
        await manager.close()
        assert manager.closed

    @pytest.mark.asyncio
    async def test_close_clears_sources(self, manager):
        """close 后 sources 应被清空."""
        manager.add_source(StubSource)
        await manager.close()
        assert manager.sources == {}

    @pytest.mark.asyncio
    async def test_close_idempotent(self, manager):
        """多次 close 不应抛出异常."""
        await manager.close()
        await manager.close()

    @pytest.mark.asyncio
    async def test_add_source_raises_after_close(self, manager):
        """close 后 add_source 应抛出 RuntimeError."""
        await manager.close()
        with pytest.raises(RuntimeError):
            manager.add_source(StubSource)

    @pytest.mark.asyncio
    async def test_start_source_starts_source(self, manager):
        """start 应调用事件源的 start 方法."""
        source = manager.add_source(StubSource)
        await manager.start()
        assert source.started
        assert source.running

    @pytest.mark.asyncio
    async def test_stop_source_stops_source(self, manager):
        """stop 应调用事件源的 stop 方法."""
        source = manager.add_source(StubSource)
        await manager.start()
        await manager.stop()
        assert source.stopped
        assert not source.running

    # ============ get_source 按类型查找（commit 2772c42）============

    def test_get_source_by_uuid(self, manager):
        """get_source(UUID) 应返回对应事件源."""
        source = manager.add_source(StubSource)
        assert manager.get_source(source.uuid) is source

    def test_get_source_by_uuid_nonexistent(self, manager):
        """get_source(UUID) 不存在的 UUID 应返回 None."""
        assert manager.get_source(UUID("00000000-0000-0000-0000-000000000000")) is None

    def test_get_source_by_type(self, manager):
        """get_source(type) 应返回该类型的唯一实例."""
        source = manager.add_source(StubSource)
        assert manager.get_source(StubSource) is source

    def test_get_source_by_type_nonexistent(self, manager):
        """get_source(type) 无该类型实例时应返回 None."""
        assert manager.get_source(StubSource) is None

    def test_get_source_by_type_returns_first(self, manager):
        """get_source(type) 有多个同类型实例时返回第一个."""
        source1 = manager.add_source(StubSource)
        manager.add_source(StubSource)  # 第二个实例
        # 返回第一个添加的
        assert manager.get_source(StubSource) is source1

    def test_get_source_by_type_distinguishes_types(self, manager):
        """get_source(type) 在不同类型间应正确区分."""
        stub = manager.add_source(StubSource)
        other = manager.add_source(OtherSource)
        assert manager.get_source(StubSource) is stub
        assert manager.get_source(OtherSource) is other

    def test_get_source_by_type_with_config_key(self, manager):
        """get_source(type, config_key) 应匹配 config_key."""
        source = manager.add_source(StubSource, config_key="mykey")
        assert manager.get_source(StubSource, "mykey") is source

    def test_get_source_by_type_with_config_key_nonexistent(self, manager):
        """get_source(type, config_key) config_key 不匹配时应返回 None."""
        manager.add_source(StubSource, config_key="key_a")
        assert manager.get_source(StubSource, "key_b") is None

    def test_get_source_by_type_config_key_among_multi(self, manager):
        """get_source(type, config_key) 在同类型多实例中应精确匹配."""
        manager.add_source(StubSource, config_key="key_a")
        target = manager.add_source(StubSource, config_key="key_b")
        manager.add_source(StubSource, config_key="key_c")
        assert manager.get_source(StubSource, "key_b") is target

    def test_get_source_by_type_without_config_key_among_multi(self, manager):
        """get_source(type) 在多实例中返回第一个，不受 config_key 影响."""
        source1 = manager.add_source(StubSource, config_key="key_a")
        manager.add_source(StubSource, config_key="key_b")
        assert manager.get_source(StubSource) is source1


class TestSourceManagerStartFailure:
    """启动失败不能留半启动状态（ARCH-002）."""

    @pytest.mark.asyncio
    async def test_start_failure_raises_source_start_error(self, manager):
        """任一事件源启动失败应抛 SourceStartError."""
        source = manager.add_source(StubSource)
        source.start_exception = RuntimeError("连接失败")

        with pytest.raises(SourceStartError):
            await manager.start()

    @pytest.mark.asyncio
    async def test_start_failure_keeps_running_false(self, manager):
        """启动失败后 running 不应为 True（原实现无条件置位）."""
        source = manager.add_source(StubSource)
        source.start_exception = RuntimeError("连接失败")

        with pytest.raises(SourceStartError):
            await manager.start()

        assert not manager.running

    @pytest.mark.asyncio
    async def test_start_failure_rolls_back_started_sources(self, manager):
        """失败时已成功启动的事件源应被回滚（stop）."""
        good = manager.add_source(StubSource)
        bad = manager.add_source(StubSource)
        bad.start_exception = RuntimeError("连接失败")

        with pytest.raises(SourceStartError):
            await manager.start()

        assert good.stopped
        assert not good.running

    @pytest.mark.asyncio
    async def test_start_failure_reports_original_exception(self, manager):
        """SourceStartError.failures 应保留原始异常."""
        original = RuntimeError("凭证过期")
        source = manager.add_source(StubSource)
        source.start_exception = original

        with pytest.raises(SourceStartError) as excinfo:
            await manager.start()

        assert original in excinfo.value.failures.values()

    @pytest.mark.asyncio
    async def test_start_aggregates_multiple_failures(self, manager):
        """多个事件源失败时应全部聚合上报."""
        first = manager.add_source(StubSource)
        second = manager.add_source(StubSource)
        first.start_exception = RuntimeError("a")
        second.start_exception = RuntimeError("b")

        with pytest.raises(SourceStartError) as excinfo:
            await manager.start()

        assert len(excinfo.value.failures) == 2

    @pytest.mark.asyncio
    async def test_failed_source_running_rolled_back(self, manager):
        """失败的事件源自身 running 也应为 False."""
        source = manager.add_source(StubSource)
        source.start_exception = RuntimeError("连接失败")

        with pytest.raises(SourceStartError):
            await manager.start()

        assert not source.running

    @pytest.mark.asyncio
    async def test_start_cancellation_rolls_back_started_sources(self, manager):
        """后续 Source 启动被取消时，已启动 Source 也必须回滚."""
        good = manager.add_source(StubSource)
        cancelled = manager.add_source(StubSource)
        cancelled.start_exception = asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await manager.start()

        assert good.stopped
        assert not good.running
        assert not cancelled.running
        assert not manager.running


class TestSourceManagerStopResilience:
    """停止流程必须尽力清理完所有事件源（ASYNC-005）."""

    @pytest.mark.asyncio
    async def test_stop_continues_after_exception(self, manager):
        """一个事件源停止失败不应中断其余事件源的清理."""
        first = manager.add_source(StubSource)
        second = manager.add_source(StubSource)
        first.stop_exception = RuntimeError("清理失败")

        await manager.start()
        await manager.stop()

        assert second.stopped
        assert not manager.running

    @pytest.mark.asyncio
    async def test_stop_continues_after_cancelled_error(self, manager):
        """CancelledError 不是 Exception 子类，也必须继续清理其余事件源."""
        first = manager.add_source(StubSource)
        second = manager.add_source(StubSource)
        first.stop_exception = asyncio.CancelledError()

        await manager.start()
        with pytest.raises(asyncio.CancelledError):
            await manager.stop()

        assert second.stopped  # 关键：第二个源没有被跳过
        assert not manager.running

    @pytest.mark.asyncio
    async def test_close_completes_cleanup_despite_cancellation(self, manager):
        """stop 因取消而抛出时，close 仍应完成清理与状态置位."""
        source = manager.add_source(StubSource)
        source.stop_exception = asyncio.CancelledError()

        await manager.start()
        with pytest.raises(asyncio.CancelledError):
            await manager.close()

        assert manager.closed
        assert manager.sources == {}


class TestSourceManagerDynamicSources:
    """运行期动态增删事件源（ARCH-001）."""

    @pytest.mark.asyncio
    async def test_add_source_while_running_binds_context(self, manager):
        """运行中新增的事件源应立即拿到上下文，以便先订阅."""
        await manager.start()
        source = manager.add_source(StubSource)
        assert source.ctx is manager.ctx

    @pytest.mark.asyncio
    async def test_add_source_while_running_does_not_auto_start(self, manager):
        """运行中新增不自动启动——否则事件会在 subscribe 注册前就开始产生."""
        await manager.start()
        source = manager.add_source(StubSource)
        assert not source.running

    @pytest.mark.asyncio
    async def test_start_source_starts_it(self, manager):
        """start_source 应启动运行期新增的事件源."""
        await manager.start()
        source = manager.add_source(StubSource)

        await manager.start_source(source)
        assert source.running
        assert source.started

    @pytest.mark.asyncio
    async def test_start_source_by_uuid(self, manager):
        """start_source 应接受 UUID."""
        await manager.start()
        source = manager.add_source(StubSource)

        await manager.start_source(source.uuid)
        assert source.running

    @pytest.mark.asyncio
    async def test_start_source_is_idempotent(self, manager):
        """重复 start_source 不应重复启动."""
        await manager.start()
        source = manager.add_source(StubSource)
        await manager.start_source(source)
        await manager.start_source(source)
        assert source.running

    @pytest.mark.asyncio
    async def test_start_source_unregistered_raises(self, manager):
        """启动未注册的事件源应抛 SourceError."""
        orphan = StubSource()
        with pytest.raises(SourceError):
            await manager.start_source(orphan)

    @pytest.mark.asyncio
    async def test_start_source_after_close_raises(self, manager):
        """已关闭后 start_source 应抛 LifecycleError."""
        source = manager.add_source(StubSource)
        source_id = source.uuid
        await manager.close()
        with pytest.raises(LifecycleError):
            await manager.start_source(source_id)

    @pytest.mark.asyncio
    async def test_stop_source_keeps_registration(self, manager):
        """stop_source 只停止，不摘除注册，可再次启动."""
        await manager.start()
        source = manager.get_source(StubSource) or manager.add_source(StubSource)
        await manager.start_source(source)

        await manager.stop_source(source)
        assert not source.running
        assert source.uuid in manager.sources

        await manager.start_source(source)
        assert source.running

    @pytest.mark.asyncio
    async def test_stop_source_unregistered_raises(self, manager):
        """停止未注册的事件源应抛 SourceError."""
        with pytest.raises(SourceError):
            await manager.stop_source(StubSource())

    @pytest.mark.asyncio
    async def test_remove_source_stops_it(self, manager):
        """remove_source 应先停止事件源，而不是只 pop（否则留下幽灵源）."""
        source = manager.add_source(StubSource)
        await manager.start()

        await manager.remove_source(source.uuid)
        assert source.stopped
        assert not source.running

    @pytest.mark.asyncio
    async def test_remove_source_purges_subscriptions(self, manager):
        """remove_source 应清掉该事件源在 EventBus 上的订阅."""
        source = manager.add_source(StubSource)
        calls: list[str] = []

        async def callback(event) -> None:
            calls.append("called")

        manager.ctx.bus.add_subscriber(source.uuid, callback, StubType.EVENT, StubType)
        assert (
            len(
                manager.ctx.bus._subscriber_group.get_callbacks(
                    source.uuid, StubType.EVENT
                )
            )
            == 1
        )

        await manager.remove_source(source.uuid)
        assert (
            manager.ctx.bus._subscriber_group.get_callbacks(source.uuid, StubType.EVENT)
            == ()
        )

    @pytest.mark.asyncio
    async def test_remove_source_survives_stop_failure(self, manager):
        """停止失败也应完成摘除与退订."""
        source = manager.add_source(StubSource)
        source.stop_exception = RuntimeError("清理失败")
        await manager.start()

        removed = await manager.remove_source(source.uuid)
        assert removed is source
        assert source.uuid not in manager.sources

    @pytest.mark.asyncio
    async def test_remove_source_cancellation_still_purges_registration(self, manager):
        """停止被取消时也必须完成退订和摘除，再传播取消."""
        source = manager.add_source(StubSource)
        await manager.start()

        async def callback(event):
            pass

        manager.ctx.bus.add_subscriber(
            source.uuid,
            callback,
            StubType.EVENT,
            StubType,
        )
        source.stop_exception = asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await manager.remove_source(source.uuid)

        assert source.uuid not in manager.sources
        assert (
            manager.ctx.bus._subscriber_group.get_callbacks(
                source.uuid,
                StubType.EVENT,
            )
            == ()
        )

    @pytest.mark.asyncio
    async def test_add_source_after_close_raises_lifecycle_error(self, manager):
        """已关闭后 add_source 应抛 LifecycleError（仍兼容 RuntimeError）."""
        await manager.close()
        with pytest.raises(LifecycleError):
            manager.add_source(StubSource)
