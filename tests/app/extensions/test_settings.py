from __future__ import annotations

import pytest

from butterbot.app.extensions.experimental import PluginSettings
from butterbot.core.exceptions import ConfigError


def test_empty_settings_disable_discovery():
    assert PluginSettings.from_mapping({}).enabled == ()


def test_enabled_order_is_preserved():
    settings = PluginSettings.from_mapping(
        {"plugins": {"enabled": ["example.two", "example.one"]}}
    )

    assert settings.enabled == ("example.two", "example.one")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"plugins": []}, "应为映射"),
        ({"plugins": {"unknown": True}}, "未知字段"),
        ({"plugins": {"enabled": "example.one"}}, "应为列表"),
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
