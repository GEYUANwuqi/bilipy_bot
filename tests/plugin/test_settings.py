"""插件配置解析测试."""

from __future__ import annotations

import pytest

from butterbot.core.exceptions import ConfigError
from butterbot.plugin import PluginSettings


def test_empty_settings_disable_discovery():
    assert PluginSettings.from_mapping({}).enabled == ()


def test_enabled_order_is_preserved():
    settings = PluginSettings.from_mapping(
        {"plugins": {"enabled": ["example.two", "example.one"]}}
    )

    assert settings.enabled == ("example.two", "example.one")


def test_local_and_private_settings_are_parsed_and_frozen():
    settings = PluginSettings.from_mapping(
        {
            "plugins": {
                "local": {"path": "./extensions", "auto_enable": True},
                "config": {
                    "local.example": {
                        "nested": {"values": [1, 2]},
                    }
                },
            }
        }
    )

    assert settings.local is not None
    assert settings.local.path == "./extensions"
    assert settings.local.auto_enable
    assert settings.requires_plugin_bootstrap
    assert settings.config_by_plugin["local.example"]["nested"] == {"values": (1, 2)}
    with pytest.raises(TypeError):
        settings.config_by_plugin["local.example"]["new"] = "value"  # type: ignore[index]


def test_private_config_alone_requires_plugin_bootstrap():
    settings = PluginSettings.from_mapping(
        {"plugins": {"config": {"local.example": {}}}}
    )

    assert settings.requires_plugin_bootstrap


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"plugins": []}, "应为映射"),
        ({"plugins": {"unknown": True}}, "未知字段"),
        ({"plugins": {"enabled": "example.one"}}, "应为列表"),
        ({"plugins": {"enabled": ["Example.One"]}}, "无效 plugin ID"),
        ({"plugins": {"local": []}}, "plugins.local"),
        ({"plugins": {"local": None}}, "plugins.local"),
        ({"plugins": {"local": {"auto_enable": "yes"}}}, "布尔值"),
        ({"plugins": {"config": []}}, "plugins.config"),
        ({"plugins": {"enabled": [" example.one"]}}, "无首尾空白"),
        (
            {"plugins": {"enabled": ["example.one", "example.one"]}},
            "重复",
        ),
    ],
)
def test_invalid_plugin_settings_are_rejected(data, message):
    with pytest.raises(ConfigError, match=message):
        PluginSettings.from_mapping(data)
