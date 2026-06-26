"""Tests for RuntimeConfig."""

from bilipy_bot.app.config import RuntimeConfig


class TestRuntimeConfig:
    """Test RuntimeConfig key-value storage."""

    def test_construction_with_kwargs(self):
        """构造函数应接受并存储 kwargs."""
        config = RuntimeConfig(key1="value1", key2=42)
        assert config.get_config("key1") == "value1"
        assert config.get_config("key2") == 42

    def test_get_config_existing_key(self):
        """get_config 应返回已存储的值."""
        config = RuntimeConfig(db_url="sqlite:///:memory:")
        assert config.get_config("db_url") == "sqlite:///:memory:"

    def test_get_config_missing_key_returns_default(self):
        """get_config 不存在的键应返回默认值 None."""
        config = RuntimeConfig()
        assert config.get_config("non_existent") is None

    def test_get_config_missing_key_returns_custom_default(self):
        """get_config 不存在的键应返回自定义默认值."""
        config = RuntimeConfig()
        assert config.get_config("non_existent", 123) == 123

    def test_empty_construction(self):
        """RuntimeConfig 可以无参数构造."""
        config = RuntimeConfig()
        assert config.get_config("any") is None
