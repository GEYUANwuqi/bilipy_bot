"""Tests for RuntimeConfig."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from butterbot.app import ConfigError
from butterbot.app.config import (
    ConfigBuilderRegistry,
    RuntimeConfig,
    register_builder,
)
from butterbot.sources.napcat import NapcatConfig


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

    @pytest.mark.parametrize("source_name", ["bilibili", "napcat"])
    def test_rejects_top_level_source_config(
        self,
        tmp_path: Path,
        source_name: str,
    ):
        """Source builder 名称不能直接作为 YAML 顶层配置键."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(f"{source_name}:\n  value: legacy\n")

        with pytest.raises(ConfigError, match="顶层 Source 配置.*不受支持"):
            RuntimeConfig.from_yaml(yaml_file, environ={})

    def test_from_yaml_builder_failure(self, tmp_path: Path):
        """构建器失败时应抛出 ValueError."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "sources:\n"
            "  qq_account:\n"
            "    source_name: napcat\n"
            "    nonexistent_field: value\n"
        )
        with pytest.raises(ValueError, match="napcat"):
            RuntimeConfig.from_yaml(yaml_file, environ={})

    def test_from_yaml_mixed(self, tmp_path: Path):
        """应同时支持已知构建器和普通键值."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "custom_key: custom_value\n"
            "sources:\n"
            "  bili_account:\n"
            "    source_name: bilibili\n"
            "    sessdata: s\n"
            "    bili_jct: j\n"
            "    buvid3: b\n"
        )
        config = RuntimeConfig.from_yaml(yaml_file, environ={})
        assert config.get_config("bili_account") is not None
        assert config.get_config("custom_key") == "custom_value"

    def test_custom_builder(self, tmp_path: Path):
        """register_builder 应该能让用户注册自定义构建器."""
        original = _get_builders_copy()

        try:
            yaml_file = tmp_path / "config.yaml"
            yaml_file.write_text(
                "sources:\n"
                "  my_instance:\n"
                "    source_name: myapp\n"
                "    host: localhost\n"
                "    port: 8080\n"
            )

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
            config = RuntimeConfig.from_yaml(yaml_file, environ={})
            myapp = config.get_config("my_instance")
            assert isinstance(myapp, MyConfig)
            assert myapp.host == "localhost"
            assert myapp.port == 8080
        finally:
            _restore_builders(original)

    @patch("butterbot.app.config.yaml.safe_load")
    def test_from_yaml_parse_error(self, mock_load, tmp_path: Path):
        """YAML 解析错误应传递原始异常."""
        import yaml

        mock_load.side_effect = yaml.YAMLError("parse error")
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("invalid: yaml: {\n")
        with pytest.raises(yaml.YAMLError):
            RuntimeConfig.from_yaml(yaml_file)


class TestNamedSourceConfig:
    """Test sources.<config_key>.source_name configuration."""

    def test_builds_named_bilibili_and_napcat_configs(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "sources:\n"
            "  bili_account:\n"
            "    source_name: bilibili\n"
            "    sessdata: sess\n"
            "    bili_jct: jct\n"
            "    buvid3: b3\n"
            "  qq_account:\n"
            "    source_name: napcat\n"
            "    url: ws://localhost:3001\n"
            "    token: token\n"
        )

        config = RuntimeConfig.from_yaml(yaml_file, environ={})

        assert config.get_config("bili_account") is not None
        napcat = config.get_config("qq_account")
        assert isinstance(napcat, NapcatConfig)
        assert napcat.url == "ws://localhost:3001"
        assert napcat.token == "token"
        assert config.get_config("sources") is None

    def test_preserves_source_definition_metadata(self, tmp_path: Path):
        """配置加载后应保留 source_name，供后续 provider 原型使用."""
        registry = ConfigBuilderRegistry()
        registry.register("example", lambda value: dict(value))
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "sources:\n  primary:\n    source_name: example\n    token: secret\n"
        )

        config = RuntimeConfig.from_yaml(
            yaml_file,
            environ={},
            builder_registry=registry,
        )
        definition = config.get_source_definition("primary")

        assert definition is not None
        assert definition.config_key == "primary"
        assert definition.source_name == "example"
        assert definition.config is config.get_config("primary")
        assert "secret" not in repr(definition)

    def test_isolated_registry_does_not_use_global_builders(self, tmp_path: Path):
        registry = ConfigBuilderRegistry()
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "sources:\n  account:\n    source_name: napcat\n    url: ws://localhost\n"
        )

        with pytest.raises(ConfigError, match="未注册的 source_name 'napcat'"):
            RuntimeConfig.from_yaml(
                yaml_file,
                environ={},
                builder_registry=registry,
            )


class TestConfigBuilderRegistry:
    def test_rejects_collision_and_supports_owned_unregister(self):
        registry = ConfigBuilderRegistry()
        first = registry.register("example", dict)

        with pytest.raises(ConfigError, match="已注册"):
            registry.register("example", list)

        replacement = registry.register("example", list, replace=True)
        assert first.unregister() is False
        assert registry.get("example") is list
        assert replacement.unregister() is True
        assert registry.get("example") is None

    def test_source_name_is_not_passed_to_builder(self, tmp_path: Path):
        original = _get_builders_copy()
        received: dict = {}

        try:
            register_builder("custom", lambda value: received.update(value) or value)
            yaml_file = tmp_path / "config.yaml"
            yaml_file.write_text(
                "sources:\n"
                "  account:\n"
                "    source_name: custom\n"
                "    endpoint: https://example.com\n"
            )

            RuntimeConfig.from_yaml(yaml_file, environ={})

            assert received == {"endpoint": "https://example.com"}
        finally:
            _restore_builders(original)

    @pytest.mark.parametrize(
        ("content", "message"),
        [
            ("sources: []\n", "'sources' 应为映射"),
            ("sources:\n  account: value\n", "'account' 应为映射"),
            (
                "sources:\n  account:\n    url: ws://localhost\n",
                "'account' 缺少非空字符串 'source_name'",
            ),
            (
                "sources:\n  account:\n    source_name: unknown\n",
                "未注册的 source_name 'unknown'",
            ),
        ],
    )
    def test_rejects_invalid_source_definitions(
        self,
        tmp_path: Path,
        content: str,
        message: str,
    ):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(content)

        with pytest.raises(ConfigError, match=message):
            RuntimeConfig.from_yaml(yaml_file, environ={})

    def test_rejects_legacy_and_named_key_collision(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "account: legacy\n"
            "sources:\n"
            "  account:\n"
            "    source_name: napcat\n"
            "    url: ws://localhost\n"
        )

        with pytest.raises(ConfigError, match="配置键 'account'.*冲突"):
            RuntimeConfig.from_yaml(yaml_file, environ={})

    def test_custom_builder_supports_multiple_named_instances(self, tmp_path: Path):
        original = _get_builders_copy()

        try:
            register_builder("custom", lambda value: dict(value))
            yaml_file = tmp_path / "config.yaml"
            yaml_file.write_text(
                "sources:\n"
                "  primary:\n"
                "    source_name: custom\n"
                "    value: one\n"
                "  secondary:\n"
                "    source_name: custom\n"
                "    value: two\n"
            )

            config = RuntimeConfig.from_yaml(yaml_file, environ={})

            assert config.get_config("primary") == {"value": "one"}
            assert config.get_config("secondary") == {"value": "two"}
        finally:
            _restore_builders(original)


class TestEnvironmentConfig:
    """Test YAML environment declaration and process environment overrides."""

    def test_resolves_process_environment_reference(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "sources:\n"
            "  qq_account:\n"
            "    source_name: napcat\n"
            "    url: ${NAPCAT_URL}\n"
            "    token: prefix-${NAPCAT_TOKEN}\n"
        )

        config = RuntimeConfig.from_yaml(
            yaml_file,
            environ={
                "NAPCAT_URL": "ws://localhost:3001",
                "NAPCAT_TOKEN": "secret",
            },
        )

        napcat = config.get_config("qq_account")
        assert napcat.url == "ws://localhost:3001"
        assert napcat.token == "prefix-secret"

    def test_reads_current_os_environment_by_default(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv("NAPCAT_URL", "ws://process:3001")
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "sources:\n  qq_account:\n    source_name: napcat\n    url: ${NAPCAT_URL}\n"
        )

        config = RuntimeConfig.from_yaml(yaml_file)

        assert config.get_config("qq_account").url == "ws://process:3001"

    def test_yaml_environment_supplies_defaults_without_mutating_os_environ(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("BUTTERBOT_TEST_TOKEN", raising=False)
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "environment:\n"
            "  BUTTERBOT_TEST_URL: ws://localhost:3001\n"
            "  BUTTERBOT_TEST_TOKEN: yaml-secret\n"
            "sources:\n"
            "  qq_account:\n"
            "    source_name: napcat\n"
            "    url: ${BUTTERBOT_TEST_URL}\n"
            "    token: ${BUTTERBOT_TEST_TOKEN}\n"
        )

        config = RuntimeConfig.from_yaml(yaml_file, environ={})

        napcat = config.get_config("qq_account")
        assert napcat.token == "yaml-secret"
        assert "BUTTERBOT_TEST_TOKEN" not in os.environ

    def test_process_environment_wins_over_yaml_environment(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "environment:\n"
            "  NAPCAT_TOKEN: yaml-secret\n"
            "sources:\n"
            "  qq_account:\n"
            "    source_name: napcat\n"
            "    url: ws://localhost:3001\n"
            "    token: ${NAPCAT_TOKEN}\n"
        )

        config = RuntimeConfig.from_yaml(
            yaml_file,
            environ={"NAPCAT_TOKEN": "process-secret"},
        )

        assert config.get_config("qq_account").token == "process-secret"

    def test_environment_default_value(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "sources:\n"
            "  qq_account:\n"
            "    source_name: napcat\n"
            "    url: ${NAPCAT_URL:-ws://localhost:3001}\n"
            "    token: ${NAPCAT_TOKEN:-}\n"
        )

        config = RuntimeConfig.from_yaml(yaml_file, environ={})

        napcat = config.get_config("qq_account")
        assert napcat.url == "ws://localhost:3001"
        assert napcat.token == ""

    def test_missing_environment_reference_raises(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("value: ${MISSING_SECRET}\n")

        with pytest.raises(ConfigError, match="MISSING_SECRET.*未设置"):
            RuntimeConfig.from_yaml(yaml_file, environ={})

    def test_yaml_environment_can_reference_process_environment(
        self,
        tmp_path: Path,
    ):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "environment:\n"
            "  API_URL: ${SCHEME}://localhost:3001\n"
            "sources:\n"
            "  qq_account:\n"
            "    source_name: napcat\n"
            "    url: ${API_URL}\n"
        )

        config = RuntimeConfig.from_yaml(yaml_file, environ={"SCHEME": "ws"})

        assert config.get_config("qq_account").url == "ws://localhost:3001"

    def test_yaml_environment_cycle_raises(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("environment:\n  FIRST: ${SECOND}\n  SECOND: ${FIRST}\n")

        with pytest.raises(ConfigError, match="循环引用"):
            RuntimeConfig.from_yaml(yaml_file, environ={})

    def test_environment_default_does_not_hide_cycle(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "environment:\n  FIRST: ${SECOND:-fallback}\n  SECOND: ${FIRST}\n"
        )

        with pytest.raises(ConfigError, match="循环引用"):
            RuntimeConfig.from_yaml(yaml_file, environ={})

    def test_environment_section_is_not_exposed_as_runtime_config(
        self,
        tmp_path: Path,
    ):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("environment:\n  LOCAL_VALUE: value\n")

        config = RuntimeConfig.from_yaml(yaml_file, environ={})

        assert config.get_config("environment") is None

    def test_hierarchical_environment_override(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "sources:\n"
            "  qq_account:\n"
            "    source_name: napcat\n"
            "    url: ws://yaml:3001\n"
            "    heartbeat: 30\n"
        )

        config = RuntimeConfig.from_yaml(
            yaml_file,
            environ={
                "BUTTERBOT__SOURCES__QQ_ACCOUNT__URL": "ws://env:3001",
                "BUTTERBOT__SOURCES__QQ_ACCOUNT__HEARTBEAT": "15.5",
                "BUTTERBOT__SOURCES__QQ_ACCOUNT__TOKEN": "secret",
            },
        )

        napcat = config.get_config("qq_account")
        assert napcat.url == "ws://env:3001"
        assert napcat.heartbeat == 15.5
        assert napcat.token == "secret"

    def test_hierarchical_environment_can_define_source(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("{}\n")

        config = RuntimeConfig.from_yaml(
            yaml_file,
            environ={
                "BUTTERBOT__SOURCES__QQ_ACCOUNT__SOURCE_NAME": "napcat",
                "BUTTERBOT__SOURCES__QQ_ACCOUNT__URL": "ws://localhost:3001",
            },
        )

        assert isinstance(config.get_config("qq_account"), NapcatConfig)

    def test_custom_environment_prefix(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("setting: yaml\n")

        config = RuntimeConfig.from_yaml(
            yaml_file,
            environ={"APP__SETTING": "environment"},
            env_prefix="APP__",
        )

        assert config.get_config("setting") == "environment"

    def test_example_config_can_be_loaded(self):
        config = RuntimeConfig.from_yaml("examples/config.example.yaml", environ={})

        assert config.get_config("bili_account") is not None
        assert isinstance(config.get_config("qq_account"), NapcatConfig)


# 测试辅助：保存和恢复 _CONFIG_BUILDERS 状态


def _get_builders_copy() -> dict:
    """获取 _CONFIG_BUILDERS 当前状态的快照."""
    from butterbot.app.config import _CONFIG_BUILDERS

    return dict(_CONFIG_BUILDERS)


def _restore_builders(original: dict) -> None:
    """恢复 _CONFIG_BUILDERS 到指定状态."""
    from butterbot.app.config import _CONFIG_BUILDERS

    _CONFIG_BUILDERS.clear()
    _CONFIG_BUILDERS.update(original)
