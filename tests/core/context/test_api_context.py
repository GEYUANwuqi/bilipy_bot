"""Tests for APIContext singleton management."""

from bilipy_bot.app.config import RuntimeConfig
from bilipy_bot.core.api import BaseApi
from bilipy_bot.core.context import APIContext


class MockApi(BaseApi):
    """Minimal API implementation for testing."""

    def __init__(self):
        self._initialized = True

    @classmethod
    def create(cls, ctx, config_key):
        return cls()


class TestAPIContext:
    """Test APIContext singleton caching and clear."""

    def setup_method(self):
        self.ctx = APIContext(RuntimeConfig())

    def test_get_api_creates_instance(self):
        """get_api 应创建指定类的实例."""
        api = self.ctx.get_api(MockApi, "test")
        assert isinstance(api, MockApi)

    def test_get_api_caches_instance(self):
        """相同类 + 相同键应返回同一对象."""
        api1 = self.ctx.get_api(MockApi, "test")
        api2 = self.ctx.get_api(MockApi, "test")
        assert api1 is api2

    def test_get_api_different_key_different_instance(self):
        """相同类 + 不同键应返回不同实例."""
        api1 = self.ctx.get_api(MockApi, "key_a")
        api2 = self.ctx.get_api(MockApi, "key_b")
        assert api1 is not api2

    def test_clear_removes_all_instances(self):
        """clear 后 get_api 应创建新实例."""
        api1 = self.ctx.get_api(MockApi, "test")
        self.ctx.clear()
        api2 = self.ctx.get_api(MockApi, "test")
        assert api1 is not api2

    def test_clear_on_empty_does_not_raise(self):
        """clear 空上下文不应抛出异常."""
        ctx = APIContext(RuntimeConfig())
        ctx.clear()  # should not raise

    def test_get_aliases_get_api(self):
        """get 应是 get_api 的别名."""
        api = self.ctx.get(MockApi, "alias")
        assert isinstance(api, MockApi)
