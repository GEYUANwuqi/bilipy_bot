"""Tests for ApiRegistry singleton management."""

import pytest

from bilipy_bot.app.config import RuntimeConfig
from bilipy_bot.core.api import BaseApi
from bilipy_bot.core.context import ApiRegistry
from bilipy_bot.core.exceptions import ConfigError


class MockApi(BaseApi):
    """Minimal API implementation for testing."""

    def __init__(self):
        self._initialized = True

    @classmethod
    def create(cls, ctx, config_key):
        return cls()


class ClosableApi(BaseApi):
    """记录 aclose 调用次数的 API."""

    instances: list["ClosableApi"] = []

    def __init__(self):
        self.close_calls = 0
        ClosableApi.instances.append(self)

    @classmethod
    def create(cls, ctx, config_key):
        return cls()

    async def aclose(self) -> None:
        self.close_calls += 1


class FailingCloseApi(BaseApi):
    """aclose 会抛异常的 API."""

    def __init__(self):
        pass

    @classmethod
    def create(cls, ctx, config_key):
        return cls()

    async def aclose(self) -> None:
        raise RuntimeError("关闭失败")


class RequiresConfigApi(BaseApi):
    """通过 require_config 读取必需配置的 API."""

    def __init__(self, config):
        self.config = config

    @classmethod
    def create(cls, ctx, config_key):
        return cls(ctx.require_config(config_key))


class NestedApi(BaseApi):
    """create 内部再取用另一个 API（会重入 ApiRegistry 的锁）."""

    def __init__(self, inner):
        self.inner = inner

    @classmethod
    def create(cls, ctx, config_key):
        return cls(ctx.get_api(MockApi, "inner"))


class TestApiRegistry:
    """Test ApiRegistry singleton caching and clear."""

    def setup_method(self):
        self.registry = ApiRegistry(RuntimeConfig())

    def test_get_api_creates_instance(self):
        """get_api 应创建指定类的实例."""
        api = self.registry.get_api(MockApi, "test")
        assert isinstance(api, MockApi)

    def test_get_api_caches_instance(self):
        """相同类 + 相同键应返回同一对象."""
        api1 = self.registry.get_api(MockApi, "test")
        api2 = self.registry.get_api(MockApi, "test")
        assert api1 is api2

    def test_get_api_different_key_different_instance(self):
        """相同类 + 不同键应返回不同实例."""
        api1 = self.registry.get_api(MockApi, "key_a")
        api2 = self.registry.get_api(MockApi, "key_b")
        assert api1 is not api2

    def test_clear_removes_all_instances(self):
        """clear 后 get_api 应创建新实例."""
        api1 = self.registry.get_api(MockApi, "test")
        self.registry.clear()
        api2 = self.registry.get_api(MockApi, "test")
        assert api1 is not api2

    def test_clear_on_empty_does_not_raise(self):
        """clear 空注册器不应抛出异常."""
        registry = ApiRegistry(RuntimeConfig())
        registry.clear()  # should not raise

    def test_get_aliases_get_api(self):
        """get 应是 get_api 的别名."""
        api = self.registry.get(MockApi, "alias")
        assert isinstance(api, MockApi)


class TestApiRegistryRequireConfig:
    """require_config 让配置缺失报出与配置有关的错误（ERR-001）."""

    def test_require_config_returns_value(self):
        """配置存在时应返回配置对象."""
        registry = ApiRegistry(RuntimeConfig(napcat={"url": "ws://x"}))
        assert registry.require_config("napcat") == {"url": "ws://x"}

    def test_require_config_missing_raises_config_error(self):
        """配置缺失时应抛 ConfigError，而不是让 None 流到深处."""
        registry = ApiRegistry(RuntimeConfig())
        with pytest.raises(ConfigError, match="napcat"):
            registry.require_config("napcat")

    def test_require_config_none_value_raises(self):
        """配置键存在但值为 None 同样应报错."""
        registry = ApiRegistry(RuntimeConfig(napcat=None))
        with pytest.raises(ConfigError):
            registry.require_config("napcat")

    def test_create_via_require_config_surfaces_config_error(self):
        """经由 get_api 触发的 create 也应抛出 ConfigError."""
        registry = ApiRegistry(RuntimeConfig())
        with pytest.raises(ConfigError, match="缺少配置键"):
            registry.get_api(RequiresConfigApi, "missing_key")


class TestApiRegistryReentrantLock:
    """create 内部再取 API 不应自死锁（LIFE-001）."""

    def test_nested_get_api_inside_create(self):
        """create → get_api 会重入同一把锁，必须能正常返回."""
        registry = ApiRegistry(RuntimeConfig())
        api = registry.get_api(NestedApi, "outer")
        assert isinstance(api.inner, MockApi)


class TestApiRegistryAcloseAll:
    """aclose_all 释放 API 持有的资源（LIFE-001）."""

    @pytest.mark.asyncio
    async def test_aclose_all_calls_aclose(self):
        """每个实例的 aclose 都应被调用一次."""
        ClosableApi.instances.clear()
        registry = ApiRegistry(RuntimeConfig())
        api = registry.get_api(ClosableApi, "test")

        await registry.aclose_all()
        assert api.close_calls == 1

    @pytest.mark.asyncio
    async def test_aclose_all_covers_every_key(self):
        """同类多 config_key 的实例都应被关闭."""
        ClosableApi.instances.clear()
        registry = ApiRegistry(RuntimeConfig())
        api_a = registry.get_api(ClosableApi, "key_a")
        api_b = registry.get_api(ClosableApi, "key_b")

        await registry.aclose_all()
        assert api_a.close_calls == 1
        assert api_b.close_calls == 1

    @pytest.mark.asyncio
    async def test_aclose_all_clears_cache(self):
        """aclose_all 后应重新创建实例."""
        ClosableApi.instances.clear()
        registry = ApiRegistry(RuntimeConfig())
        api1 = registry.get_api(ClosableApi, "test")

        await registry.aclose_all()
        api2 = registry.get_api(ClosableApi, "test")
        assert api1 is not api2

    @pytest.mark.asyncio
    async def test_aclose_all_survives_failing_aclose(self):
        """单个 API 关闭失败不应影响其余 API 的关闭."""
        ClosableApi.instances.clear()
        registry = ApiRegistry(RuntimeConfig())
        registry.get_api(FailingCloseApi, "bad")
        good = registry.get_api(ClosableApi, "good")

        await registry.aclose_all()  # 不应抛出
        assert good.close_calls == 1

    @pytest.mark.asyncio
    async def test_aclose_all_is_idempotent(self):
        """重复 aclose_all 不应抛出，也不应重复关闭同一实例."""
        ClosableApi.instances.clear()
        registry = ApiRegistry(RuntimeConfig())
        api = registry.get_api(ClosableApi, "test")

        await registry.aclose_all()
        await registry.aclose_all()
        assert api.close_calls == 1

    @pytest.mark.asyncio
    async def test_default_aclose_is_noop(self):
        """未覆写 aclose 的 API 也应能被 aclose_all 正常处理."""
        registry = ApiRegistry(RuntimeConfig())
        registry.get_api(MockApi, "test")
        await registry.aclose_all()  # 不应抛出

    def test_clear_does_not_call_aclose(self):
        """clear 只丢引用，不应调用 aclose（那是 aclose_all 的职责）."""
        ClosableApi.instances.clear()
        registry = ApiRegistry(RuntimeConfig())
        api = registry.get_api(ClosableApi, "test")
        registry.clear()
        assert api.close_calls == 0
