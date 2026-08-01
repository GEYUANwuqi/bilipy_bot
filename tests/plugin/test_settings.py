"""插件配置解析测试."""

from __future__ import annotations

import pytest

from butterbot.core.exceptions import ConfigError
from butterbot.plugin.discovery.settings import PluginSettings


def test_empty_settings_disable_discovery():
    settings = PluginSettings.from_mapping({})

    assert not settings.enabled
    assert settings.plugin_list == ()
    assert settings.plugin_path == "./plugins"


def test_plugin_list_order_is_preserved():
    settings = PluginSettings.from_mapping(
        {
            "plugins": {
                "enabled": True,
                "plugin_list": ["ExampleTwoPlugin", "示例一插件"],
            }
        }
    )

    assert settings.enabled
    assert settings.plugin_list == ("ExampleTwoPlugin", "示例一插件")


def test_local_and_private_settings_are_parsed_and_frozen():
    settings = PluginSettings.from_mapping(
        {
            "plugins": {
                "enabled": True,
                "plugin_path": "./extensions",
                "config": {
                    "local.example": {
                        "nested": {"values": [1, 2]},
                    }
                },
            }
        }
    )

    assert settings.local.path == "./extensions"
    assert settings.plugin_path == "./extensions"
    assert settings.requires_plugin_bootstrap
    assert settings.config_by_plugin["local.example"]["nested"] == {"values": (1, 2)}
    with pytest.raises(TypeError):
        settings.config_by_plugin["local.example"]["new"] = "value"  # type: ignore[index]


def test_private_config_alone_does_not_enable_plugin_system():
    settings = PluginSettings.from_mapping(
        {"plugins": {"config": {"local.example": {}}}}
    )

    assert not settings.requires_plugin_bootstrap


def test_lifecycle_timeouts_are_parsed():
    settings = PluginSettings.from_mapping(
        {
            "plugins": {
                "lifecycle": {
                    "start_timeout": 1,
                    "stop_timeout": 2.5,
                    "cleanup_timeout": 3,
                    "drain_timeout": 4,
                }
            }
        }
    )

    assert settings.lifecycle.start_timeout == 1
    assert settings.lifecycle.stop_timeout == 2.5
    assert settings.lifecycle.cleanup_timeout == 3
    assert settings.lifecycle.drain_timeout == 4


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"plugins": []}, "应为映射"),
        ({"plugins": {"unknown": True}}, "未知字段"),
        ({"plugins": {"enabled": []}}, "布尔值"),
        ({"plugins": {"plugin_list": "ExamplePlugin"}}, "应为列表"),
        ({"plugins": {"plugin_list": [""]}}, "无效 plugin_name"),
        ({"plugins": {"plugin_path": []}}, "plugins.plugin_path"),
        ({"plugins": {"plugin_path": " ./plugins"}}, "plugins.plugin_path"),
        ({"plugins": {"config": []}}, "plugins.config"),
        ({"plugins": {"lifecycle": []}}, "plugins.lifecycle"),
        (
            {"plugins": {"lifecycle": {"start_timeout": 0}}},
            "大于 0",
        ),
        (
            {"plugins": {"lifecycle": {"unknown": 1}}},
            "未知字段",
        ),
        ({"plugins": {"plugin_list": ["Example Plugin"]}}, "无效 plugin_name"),
        (
            {"plugins": {"plugin_list": ["ExamplePlugin", "ExamplePlugin"]}},
            "重复",
        ),
    ],
)
def test_invalid_plugin_settings_are_rejected(data, message):
    with pytest.raises(ConfigError, match=message):
        PluginSettings.from_mapping(data)
