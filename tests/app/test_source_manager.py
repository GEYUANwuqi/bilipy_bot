"""Tests for SourceManager lifecycle management."""

from uuid import UUID

import pytest

from bilipy_bot.app.config import RuntimeConfig
from bilipy_bot.app.source_manager import SourceManager
from bilipy_bot.core.context import AppContext
from bilipy_bot.core.source import BaseSource


class StubSource(BaseSource):
    """Minimal concrete source for testing SourceManager."""

    def __init__(self, uuid: UUID | None = None, **kwargs):
        super().__init__(uuid=uuid)
        self.started = False
        self.stopped = False
        self.start_exception: Exception | None = None

    async def start(self):
        if self.start_exception:
            raise self.start_exception
        self.started = True
        self.running = True

    async def stop(self):
        self.stopped = True
        self.running = False


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

    def test_add_source_raises_when_closed(self, manager):
        """close 后添加事件源应抛出 RuntimeError."""
        import asyncio

        asyncio.run(manager.close())
        with pytest.raises(RuntimeError, match="已关闭"):
            manager.add_source(StubSource)

    def test_remove_source_removes_and_returns(self, manager):
        """remove_source 应移除并返回事件源."""
        source = manager.add_source(StubSource)
        removed = manager.remove_source(source.uuid)
        assert removed is source
        assert source.uuid not in manager.sources

    def test_remove_source_nonexistent_returns_none(self, manager):
        """remove_source 不存在的 UUID 应返回 None."""
        result = manager.remove_source(UUID("00000000-0000-0000-0000-000000000000"))
        assert result is None

    def test_get_source_returns_instance(self, manager):
        """get_source 应返回已添加的事件源."""
        source = manager.add_source(StubSource)
        assert manager.get_source(source.uuid) is source

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
