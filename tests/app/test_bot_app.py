"""Tests for BotApp delegation and lifecycle."""

import asyncio
import signal
import sys
from uuid import UUID

import pytest

from butter_bot.app import BotApp
from butter_bot.app.config import RuntimeConfig
from butter_bot.core.api import BaseApi
from butter_bot.core.context import ApiRegistry, AppContext
from butter_bot.core.data import BaseDataMixin
from butter_bot.core.event import Event, EventBus
from butter_bot.core.source import BaseSource
from butter_bot.core.types import BaseType


class MockType(BaseType):
    ALL = "mock.all"
    EVENT = "mock.event"


class StubSource(BaseSource):
    """Minimal source for testing BotApp delegation."""

    supported_types = MockType

    def __init__(self, uuid: UUID | None = None, **kwargs):
        super().__init__(uuid=uuid, **kwargs)
        self.started = False
        self.stopped = False

    async def on_start(self):
        self.started = True

    async def on_stop(self):
        self.stopped = True


class MockApi(BaseApi):
    """Minimal API for testing delegation."""

    def __init__(self):
        pass

    @classmethod
    def create(cls, ctx, config_key):
        return cls()


class MockData(BaseDataMixin):
    def __init__(self, value: str = "") -> None:
        self.value = value


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
        from butter_bot.app.source_manager import SourceManager

        assert isinstance(app.manager, SourceManager)

    def test_construction_no_config_raises_file_not_found(self):
        """无 config 且无 config.yaml 文件时抛出 FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="config.yaml"):
            BotApp()

    def test_construction_with_injected_ctx(self, config):
        """注入的 AppContext 应被使用."""
        api_ctx = ApiRegistry(config)
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
        """api_ctx 属性应返回 ApiRegistry."""
        assert isinstance(app.api_ctx, ApiRegistry)

    def test_add_source(self, app):
        """add_source 应委托给 SourceManager 并返回实例."""
        source = app.add_source(StubSource)
        assert isinstance(source, StubSource)
        assert app.get_source(source.uuid) is source

    @pytest.mark.asyncio
    async def test_remove_source(self, app):
        """remove_source 应委托给 SourceManager."""
        source = app.add_source(StubSource)
        removed = await app.remove_source(source.uuid)
        assert removed is source
        assert app.get_source(source.uuid) is None

    def test_get_api(self, app):
        """get_api 应委托给 ApiRegistry."""
        api = app.get_api(MockApi, "test")
        assert isinstance(api, MockApi)

    def test_subscribe_adds_subscriber(self, app):
        """subscribe 应注册订阅者到 EventBus."""
        source = app.add_source(StubSource)

        @app.subscribe(source.uuid, MockType.EVENT)
        async def handler(event):
            pass

        # Verify it was registered
        callbacks = app.bus._subscriber_group.get_callbacks(source.uuid, MockType.EVENT)
        assert len(callbacks) == 1

    def test_add_subscriber(self, app):
        """add_subscriber 应注册订阅者."""
        source = app.add_source(StubSource)

        async def callback(event):
            pass

        app.add_subscriber(source.uuid, callback, MockType.ALL)
        callbacks = app.bus._subscriber_group.get_callbacks(source.uuid, MockType.EVENT)
        assert len(callbacks) == 1

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


class TestBotAppCloseOrder:
    """close 必须按 sources → bus → apis 的固定顺序释放（ASYNC-001 / LIFE-001）."""

    @pytest.mark.asyncio
    async def test_close_closes_bus(self, config):
        """close 之后 EventBus 应处于已关闭状态."""
        app = BotApp(config)
        await app.start()
        await app.close()
        assert app.bus.closed

    @pytest.mark.asyncio
    async def test_close_drains_pending_callbacks(self, config):
        """close 应等待 in-flight 回调跑完，而不是留下 pending task."""
        app = BotApp(config)
        source = app.add_source(StubSource)
        finished: list[str] = []

        @app.subscribe(source.uuid, MockType.EVENT)
        async def handler(event):
            await asyncio.sleep(0.05)
            finished.append("done")

        await app.start()
        await app.bus.publish(
            source.uuid, Event(data=MockData(), status=MockType.EVENT)
        )
        await app.close()

        assert finished == ["done"]
        assert app.bus.pending_callbacks == 0

    @pytest.mark.asyncio
    async def test_close_releases_api_resources(self, config):
        """close 应调用每个 API 的 aclose."""
        closed: list[str] = []

        class ClosableApi(BaseApi):
            def __init__(self):
                pass

            @classmethod
            def create(cls, ctx, config_key):
                return cls()

            async def aclose(self) -> None:
                closed.append("api")

        app = BotApp(config)
        app.get_api(ClosableApi, "test")
        await app.start()
        await app.close()

        assert closed == ["api"]

    @pytest.mark.asyncio
    async def test_close_order_sources_then_bus_then_apis(self, config):
        """顺序断言：停源时总线还没关，关 API 时总线已经关."""
        observed: list[str] = []
        app = BotApp(config)

        class OrderedSource(BaseSource):
            supported_types = MockType

            async def on_start(self):
                pass

            async def on_stop(self):
                observed.append("source_stop:bus_closed=%s" % app.bus.closed)

        class OrderedApi(BaseApi):
            def __init__(self):
                pass

            @classmethod
            def create(cls, ctx, config_key):
                return cls()

            async def aclose(self) -> None:
                observed.append("api_close:bus_closed=%s" % app.bus.closed)

        app.add_source(OrderedSource)
        app.get_api(OrderedApi, "test")
        await app.start()
        await app.close()

        assert observed == [
            "source_stop:bus_closed=False",
            "api_close:bus_closed=True",
        ]

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self, config):
        """重复 close 不应抛出异常."""
        app = BotApp(config)
        await app.start()
        await app.close()
        await app.close()
        assert app.closed

    @pytest.mark.asyncio
    async def test_close_releases_apis_even_if_source_stop_cancelled(self, config):
        """停源被取消时，总线与 API 仍应在 finally 中被释放."""
        closed: list[str] = []

        class CancellingSource(BaseSource):
            supported_types = MockType

            async def on_start(self):
                pass

            async def on_stop(self):
                raise asyncio.CancelledError()

        class ClosableApi(BaseApi):
            def __init__(self):
                pass

            @classmethod
            def create(cls, ctx, config_key):
                return cls()

            async def aclose(self) -> None:
                closed.append("api")

        app = BotApp(config)
        app.add_source(CancellingSource)
        app.get_api(ClosableApi, "test")
        await app.start()

        with pytest.raises(asyncio.CancelledError):
            await app.close()

        assert app.bus.closed
        assert closed == ["api"]


class TestBotAppUnsubscribe:
    """退订 API（ARCH-001）."""

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_callbacks(self, app):
        """unsubscribe 后回调不应再被触发."""
        source = app.add_source(StubSource)
        calls: list[str] = []

        @app.subscribe(source.uuid, MockType.EVENT)
        async def handler(event):
            calls.append("called")

        assert app.unsubscribe(source.uuid) == 1

        await app.bus.publish(
            source.uuid, Event(data=MockData(), status=MockType.EVENT)
        )
        await asyncio.sleep(0)
        assert calls == []

    def test_unsubscribe_unknown_source_returns_zero(self, app, fixed_uuid):
        """未订阅过的事件源应返回 0."""
        assert app.unsubscribe(fixed_uuid) == 0


class TestBotAppDynamicSources:
    """运行期动态接入事件源（ARCH-001）."""

    @pytest.mark.asyncio
    async def test_add_subscribe_start_flow(self, config):
        """add_source → subscribe → start_source 的完整运行期接入流程."""
        app = BotApp(config)
        await app.start()

        source = app.add_source(StubSource)
        received: list[str] = []

        @app.subscribe(source.uuid, MockType.EVENT)
        async def handler(event):
            received.append(event.data.value)

        await app.start_source(source)
        assert source.running

        await app.bus.publish(
            source.uuid, Event(data=MockData("payload"), status=MockType.EVENT)
        )
        await asyncio.sleep(0)
        assert received == ["payload"]
        await app.close()

    @pytest.mark.asyncio
    async def test_stop_source_then_restart(self, config):
        """stop_source 后可再次 start_source."""
        app = BotApp(config)
        source = app.add_source(StubSource)
        await app.start()

        await app.stop_source(source)
        assert not source.running

        await app.start_source(source)
        assert source.running
        await app.close()


class TestBotAppRun:
    """阻塞式 run 入口与信号处理（ASYNC-005）."""

    def test_run_with_duration_closes_app(self, config):
        """run(duration) 到时应正常退出并完成关闭."""
        app = BotApp(config)
        source = app.add_source(StubSource)
        app.run(duration=0.01)

        assert source.started
        assert source.stopped
        assert app.closed
        assert app.bus.closed

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows 的事件循环不支持 add_signal_handler",
    )
    def test_run_sigterm_triggers_graceful_close(self, config):
        """SIGTERM 应走完整关闭路径，而不是直接杀掉进程.

        原实现只捕获 KeyboardInterrupt，容器里 docker stop / k8s 缩容发来的
        SIGTERM 会让进程直接死掉，清理代码一行都不执行。
        """
        app = BotApp(config)

        class SignallingSource(BaseSource):
            supported_types = MockType

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.stopped = False

            async def on_start(self):
                # 此时信号处理器已注册（run 在 async with 之前安装）
                loop = asyncio.get_running_loop()
                loop.call_later(0.02, signal.raise_signal, signal.SIGTERM)

            async def on_stop(self):
                self.stopped = True

        source = app.add_source(SignallingSource)
        app.run()  # 无 duration：只能由信号唤醒，否则测试会挂住

        assert source.stopped
        assert app.closed
        assert app.bus.closed
