"""Tests for RuntimeConfig."""

from pathlib import Path
from unittest.mock import patch

import pytest

from butter_bot.app.config import RuntimeConfig, register_builder


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


class TestRuntimeConfigFromYaml:
    """Test RuntimeConfig.from_yaml()."""

    def test_from_yaml_basic(self, tmp_path: Path):
        """from_yaml 应正确解析简单键值."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("key1: value1\nkey2: 42\n")
        config = RuntimeConfig.from_yaml(yaml_file)
        assert config.get_config("key1") == "value1"
        assert config.get_config("key2") == 42

    def test_from_yaml_default_path(self):
        """from_yaml 默认路径应为 'config.yaml'."""
        with pytest.raises(FileNotFoundError):
            RuntimeConfig.from_yaml()

    def test_from_yaml_file_not_found(self, tmp_path: Path):
        """配置文件不存在时应抛出 FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            RuntimeConfig.from_yaml(tmp_path / "nonexistent.yaml")

    def test_from_yaml_invalid_top_level(self, tmp_path: Path):
        """顶层不是 mapping 时应抛出 ValueError."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("[1, 2, 3]\n")
        with pytest.raises(ValueError, match="顶层应为映射"):
            RuntimeConfig.from_yaml(yaml_file)

    def test_from_yaml_empty(self, tmp_path: Path):
        """空映射应返回空的 RuntimeConfig."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("{}\n")
        config = RuntimeConfig.from_yaml(yaml_file)
        assert config.get_config("anything") is None

    def test_from_yaml_with_bilibili_builder(self, tmp_path: Path):
        """bilibili 配置项应构建为 Credential 对象."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "bilibili:\n  sessdata: sess\n  bili_jct: jct\n  buvid3: b3\n"
        )
        config = RuntimeConfig.from_yaml(yaml_file)
        cred = config.get_config("bilibili")
        # Credential 对象应该有对应的属性
        assert cred is not None

    def test_from_yaml_with_napcat_builder(self, tmp_path: Path):
        """napcat 配置项应构建为 NapcatConfig 对象."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("napcat:\n  url: ws://localhost:3001\n  token: abc\n")
        config = RuntimeConfig.from_yaml(yaml_file)
        napcat = config.get_config("napcat")
        assert napcat is not None
        assert napcat.url == "ws://localhost:3001"
        assert napcat.token == "abc"

    def test_from_yaml_builder_failure(self, tmp_path: Path):
        """构建器失败时应抛出 ValueError."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("napcat:\n  nonexistent_field: value\n")  # 缺少必填 url
        with pytest.raises(ValueError, match="napcat"):
            RuntimeConfig.from_yaml(yaml_file)

    def test_from_yaml_mixed(self, tmp_path: Path):
        """应同时支持已知构建器和普通键值."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "bilibili:\n  sessdata: s\n  bili_jct: j\n  buvid3: b\n"
            "custom_key: custom_value\n"
        )
        config = RuntimeConfig.from_yaml(yaml_file)
        assert config.get_config("bilibili") is not None
        assert config.get_config("custom_key") == "custom_value"

    def test_custom_builder(self, tmp_path: Path):
        """register_builder 应该能让用户注册自定义构建器."""
        original = _get_builders_copy()

        try:
            yaml_file = tmp_path / "config.yaml"
            yaml_file.write_text("myapp:\n  host: localhost\n  port: 8080\n")

            class MyConfig:
                def __init__(self, host: str, port: int):
                    self.host = host
                    self.port = port

                @classmethod
                def from_dict(cls, d: dict) -> "MyConfig":
                    return cls(**d)

            def builder(value: dict) -> MyConfig:
                return MyConfig(**value)

            register_builder("myapp", builder)
            config = RuntimeConfig.from_yaml(yaml_file)
            myapp = config.get_config("myapp")
            assert isinstance(myapp, MyConfig)
            assert myapp.host == "localhost"
            assert myapp.port == 8080
        finally:
            _restore_builders(original)

    @patch("butter_bot.app.config.yaml.safe_load")
    def test_from_yaml_parse_error(self, mock_load, tmp_path: Path):
        """YAML 解析错误应传递原始异常."""
        import yaml

        mock_load.side_effect = yaml.YAMLError("parse error")
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("invalid: yaml: {\n")
        with pytest.raises(yaml.YAMLError):
            RuntimeConfig.from_yaml(yaml_file)


# 测试辅助：保存和恢复 _CONFIG_BUILDERS 状态


def _get_builders_copy() -> dict:
    """获取 _CONFIG_BUILDERS 当前状态的快照."""
    from butter_bot.app.config import _CONFIG_BUILDERS

    return dict(_CONFIG_BUILDERS)


def _restore_builders(original: dict) -> None:
    """恢复 _CONFIG_BUILDERS 到指定状态."""
    from butter_bot.app.config import _CONFIG_BUILDERS

    _CONFIG_BUILDERS.clear()
    _CONFIG_BUILDERS.update(original)
