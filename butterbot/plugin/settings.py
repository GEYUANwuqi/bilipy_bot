from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from butterbot.core.exceptions import ConfigError

from .descriptor import validate_plugin_id
from .errors import PluginCompatibilityError


@dataclass(frozen=True, slots=True)
class LocalPluginSettings:
    """本地目录插件来源设置."""

    path: str = "./plugins"
    auto_enable: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.path, str)
            or not self.path
            or self.path != self.path.strip()
        ):
            raise ConfigError(
                "配置项 'plugins.local.path' 应为非空且无首尾空白的字符串"
            )
        if not isinstance(self.auto_enable, bool):
            raise ConfigError("配置项 'plugins.local.auto_enable' 应为布尔值")


@dataclass(frozen=True, slots=True)
class PluginSettings:
    """YAML ``plugins`` 保留段中的启动期插件设置."""

    enabled: tuple[str, ...] = ()
    local: LocalPluginSettings | None = None
    config_by_plugin: Mapping[str, Mapping[str, object]] = field(
        default_factory=lambda: MappingProxyType({})
    )

    @property
    def requires_plugin_bootstrap(self) -> bool:
        """配置是否选择了插件控制面，而非旧的已构造 BotApp 路径."""
        return bool(self.enabled or self.local is not None or self.config_by_plugin)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PluginSettings":
        raw_plugins = data.get("plugins", {})
        if not isinstance(raw_plugins, Mapping):
            raise ConfigError("配置项 'plugins' 应为映射")

        unknown = sorted(set(raw_plugins) - {"config", "enabled", "local"})
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
            enabled.append(_validate_config_plugin_id(plugin_id, "plugins.enabled"))
        if len(set(enabled)) != len(enabled):
            raise ConfigError("配置项 'plugins.enabled' 包含重复 plugin ID")

        local = (
            _parse_local_settings(raw_plugins["local"])
            if "local" in raw_plugins
            else None
        )
        config_by_plugin = _parse_plugin_config(raw_plugins.get("config", {}))
        return cls(
            enabled=tuple(enabled),
            local=local,
            config_by_plugin=config_by_plugin,
        )


def _parse_local_settings(value: object) -> LocalPluginSettings:
    if not isinstance(value, Mapping):
        raise ConfigError("配置项 'plugins.local' 应为映射")
    unknown = sorted(set(value) - {"auto_enable", "path"})
    if unknown:
        raise ConfigError(
            "配置项 'plugins.local' 包含未知字段: %s" % ", ".join(unknown)
        )
    path = value.get("path", "./plugins")
    if not isinstance(path, str) or not path or path != path.strip():
        raise ConfigError("配置项 'plugins.local.path' 应为非空且无首尾空白的字符串")
    auto_enable = value.get("auto_enable", False)
    if not isinstance(auto_enable, bool):
        raise ConfigError("配置项 'plugins.local.auto_enable' 应为布尔值")
    return LocalPluginSettings(path=path, auto_enable=auto_enable)


def _parse_plugin_config(
    value: object,
) -> Mapping[str, Mapping[str, object]]:
    if not isinstance(value, Mapping):
        raise ConfigError("配置项 'plugins.config' 应为映射")
    result: dict[str, Mapping[str, object]] = {}
    for plugin_id, plugin_config in value.items():
        if (
            not isinstance(plugin_id, str)
            or not plugin_id
            or plugin_id != plugin_id.strip()
        ):
            raise ConfigError(
                "plugins.config 的 plugin ID 必须是非空且无首尾空白的字符串"
            )
        plugin_id = _validate_config_plugin_id(plugin_id, "plugins.config")
        if not isinstance(plugin_config, Mapping):
            raise ConfigError("配置项 'plugins.config.%s' 应为映射" % plugin_id)
        result[plugin_id] = _freeze_mapping(plugin_config)
    return MappingProxyType(result)


def _freeze_mapping(value: Mapping[object, object]) -> Mapping[str, object]:
    frozen: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ConfigError("插件私有配置键必须是字符串")
        frozen[key] = _freeze(item)
    return MappingProxyType(frozen)


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _validate_config_plugin_id(value: str, path: str) -> str:
    try:
        return validate_plugin_id(value)
    except PluginCompatibilityError as exc:
        raise ConfigError("%s 包含无效 plugin ID: %s" % (path, value)) from exc


__all__ = [
    "LocalPluginSettings",
    "PluginSettings",
]
