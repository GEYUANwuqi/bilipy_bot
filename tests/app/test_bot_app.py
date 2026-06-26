"""Tests for BotApp delegation and lifecycle."""

from uuid import UUID

import pytest

from bilipy_bot.app import BotApp
from bilipy_bot.app.config import RuntimeConfig
from bilipy_bot.core.api import BaseApi
from bilipy_bot.core.context import APIContext, AppContext
from bilipy_bot.core.data import BaseDataMixin
from bilipy_bot.core.event import EventBus
from bilipy_bot.core.source import BaseSource
from bilipy_bot.core.types import BaseType


class StubSource(BaseSource):
    """Minimal source for testing BotApp delegation."""

    def __init__(self, uuid: UUID | None = None, **kwargs):
        super().__init__(uuid=uuid)
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True
        self.running = True

    async def stop(self):
        self.stopped = True
        self.running = False


class MockApi(BaseApi):
    """Minimal API for testing delegation."""

    def __init__(self):
        pass

    @classmethod
    def create(cls, ctx, config_key):
        return cls()


class MockType(BaseType):
    ALL = "mock.all"
    EVENT = "mock.event"


class MockData(BaseDataMixin):
    value: str = ""


@pytest.fixture
def config():
    return RuntimeConfig(test="value")


@pytest.fixture
def app(config):
    return BotApp(config)


class TestBotApp:
    """Test BotApp construction, delegation, and lifecycle."""

    def test_construction_with_config(self, config):
        """传入 config 构造应创建内部的 AppContext 和 SourceManager."""
        app = BotApp(config)
        assert isinstance(app.ctx, AppContext)
        from bilipy_bot.app.source_manager import SourceManager

        assert isinstance(app.manager, SourceManager)

    def test_construction_no_config_raises_file_not_found(self):
        """无 config 且无 config.yaml 文件时抛出 FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="config.yaml"):
            BotApp()

    def test_construction_with_injected_ctx(self, config):
        """注入的 AppContext 应被使用."""
        api_ctx = APIContext(config)
        bus = EventBus()
        ctx = AppContext(config, event_bus=bus, api_ctx=api_ctx)
        app = BotApp(config, ctx=ctx)
        assert app.ctx is ctx
        assert app.bus is bus

    def test_config_property(self, config, app):
        """config 属性应返回 RuntimeConfig."""
        assert app.config is config

    def test_ctx_property(self, app):
        """ctx 属性应返回 AppContext."""
        assert isinstance(app.ctx, AppContext)

    def test_bus_property(self, app):
        """bus 属性应返回 EventBus."""
        assert isinstance(app.bus, EventBus)

    def test_manager_property(self, app):
        """manager 属性应返回 SourceManager."""
        assert app.manager is not None

    def test_api_ctx_property(self, app):
        """api_ctx 属性应返回 APIContext."""
        assert isinstance(app.api_ctx, APIContext)

    def test_add_source(self, app):
        """add_source 应委托给 SourceManager 并返回实例."""
        source = app.add_source(StubSource)
        assert isinstance(source, StubSource)
        assert app.get_source(source.uuid) is source

    def test_remove_source(self, app):
        """remove_source 应委托给 SourceManager."""
        source = app.add_source(StubSource)
        removed = app.remove_source(source.uuid)
        assert removed is source
        assert app.get_source(source.uuid) is None

    def test_get_api(self, app):
        """get_api 应委托给 APIContext."""
        api = app.get_api(MockApi, "test")
        assert isinstance(api, MockApi)

    def test_subscribe_adds_subscriber(self, app):
        """subscribe 应注册订阅者到 EventBus."""
        source = app.add_source(StubSource)

        @app.subscribe(source.uuid, MockType.EVENT)
        async def handler(event):
            pass

        # Verify it was registered
        subs = app.bus._subscriber_group.get_subscriber(source.uuid)
        assert len(subs) == 1

    def test_add_subscriber(self, app):
        """add_subscriber 应注册订阅者."""
        source = app.add_source(StubSource)

        async def callback(event):
            pass

        app.add_subscriber(source.uuid, callback, MockType.ALL)
        subs = app.bus._subscriber_group.get_subscriber(source.uuid)
        assert len(subs) == 1

    def test_running_property_initially_false(self, app):
        """初始 running 应为 False."""
        assert not app.running

    def test_closed_property_initially_false(self, app):
        """初始 closed 应为 False."""
        assert not app.closed

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, app):
        """start/stop 应改变 running 状态."""
        assert not app.running
        await app.start()
        assert app.running
        await app.stop()
        assert not app.running

    @pytest.mark.asyncio
    async def test_async_context_manager(self, app):
        """async with 应调用 start/close."""
        async with app:
            assert app.running
        assert not app.running
        assert app.closed
