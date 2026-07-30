from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from butterbot.core.exceptions import ConfigError


@dataclass(frozen=True, slots=True)
class PluginSettings:
    """YAML ``plugins`` 保留段中的最小启动设置."""

    enabled: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PluginSettings":
        raw_plugins = data.get("plugins", {})
        if not isinstance(raw_plugins, Mapping):
            raise ConfigError("配置项 'plugins' 应为映射")

        unknown = sorted(set(raw_plugins) - {"enabled"})
        if unknown:
            raise ConfigError("配置项 'plugins' 包含未知字段: %s" % ", ".join(unknown))

        raw_enabled = raw_plugins.get("enabled", [])
        if not isinstance(raw_enabled, list):
            raise ConfigError("配置项 'plugins.enabled' 应为列表")

        enabled: list[str] = []
        for plugin_id in raw_enabled:
            if (
                not isinstance(plugin_id, str)
                or not plugin_id
                or plugin_id != plugin_id.strip()
            ):
                raise ConfigError(
                    "plugins.enabled 中的 plugin ID 必须是非空且无首尾空白的字符串"
                )
            enabled.append(plugin_id)
        if len(set(enabled)) != len(enabled):
            raise ConfigError("配置项 'plugins.enabled' 包含重复 plugin ID")
        return cls(tuple(enabled))


__all__ = ["PluginSettings"]
