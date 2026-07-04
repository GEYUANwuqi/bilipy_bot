"""Tests for AppContext construction and DI."""

from bilipy_bot.app.config import RuntimeConfig
from bilipy_bot.core.context import ApiRegistry, AppContext
from bilipy_bot.core.event import EventBus


class TestAppContext:
    """Test AppContext default construction and injection."""

    def test_construction_with_config(self):
        """默认构造应创建内部的 EventBus 和 ApiRegistry."""
        config = RuntimeConfig(test="value")
        ctx = AppContext(config)
        assert ctx.config is config
        assert isinstance(ctx.bus, EventBus)
        assert isinstance(ctx.api_ctx, ApiRegistry)

    def test_config_property(self):
        """config 属性应返回传入的 RuntimeConfig."""
        config = RuntimeConfig(key="val")
        ctx = AppContext(config)
        assert ctx.config == config
        assert ctx.config.get_config("key") == "val"

    def test_bus_property(self):
        """bus 属性应返回 EventBus 实例."""
        ctx = AppContext(RuntimeConfig())
        assert isinstance(ctx.bus, EventBus)

    def test_api_ctx_property(self):
        """api_ctx 属性应返回 ApiRegistry 实例."""
        ctx = AppContext(RuntimeConfig())
        assert isinstance(ctx.api_ctx, ApiRegistry)

    def test_construction_with_injected_event_bus(self):
        """注入 EventBus 应被 bus 属性返回."""
        config = RuntimeConfig()
        bus = EventBus()
        ctx = AppContext(config, event_bus=bus)
        assert ctx.bus is bus

    def test_construction_with_injected_api_ctx(self):
        """注入 ApiRegistry 应被 api_ctx 属性返回."""
        config = RuntimeConfig()
        api_ctx = ApiRegistry(config)
        ctx = AppContext(config, api_ctx=api_ctx)
        assert ctx.api_ctx is api_ctx

    def test_inject_both(self):
        """同时注入 EventBus 和 ApiRegistry."""
        config = RuntimeConfig()
        bus = EventBus()
        api_ctx = ApiRegistry(config)
        ctx = AppContext(config, event_bus=bus, api_ctx=api_ctx)
        assert ctx.bus is bus
        assert ctx.api_ctx is api_ctx
