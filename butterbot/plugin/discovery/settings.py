from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any

from butterbot.core.exceptions import ConfigError
from butterbot.plugin.contracts.identifiers import (
    validate_plugin_id,
    validate_plugin_name,
)
from butterbot.plugin.errors import PluginCompatibilityError


@dataclass(frozen=True, slots=True)
class LocalPluginSettings:
    """本地目录插件来源设置."""

    path: str = "./plugins"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.path, str)
            or not self.path
            or self.path != self.path.strip()
        ):
            raise ConfigError(
                "配置项 'plugins.plugin_path' 应为非空且无首尾空白的字符串"
            )


@dataclass(frozen=True, slots=True)
class PluginLifecyclePolicy:
    """单个插件生命周期阶段的超时策略."""

    start_timeout: float = 30.0
    stop_timeout: float = 10.0
    cleanup_timeout: float = 10.0
    drain_timeout: float = 5.0

    def __post_init__(self) -> None:
        for name, value in (
            ("start_timeout", self.start_timeout),
            ("stop_timeout", self.stop_timeout),
            ("cleanup_timeout", self.cleanup_timeout),
            ("drain_timeout", self.drain_timeout),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or value <= 0
            ):
                raise ConfigError(
                    "配置项 'plugins.lifecycle.%s' 应为大于 0 的有限数字" % name
                )


@dataclass(frozen=True, slots=True)
class PluginSettings:
    """YAML ``plugins`` 保留段中的启动期插件设置."""

    enabled: bool = False
    plugin_list: tuple[str, ...] = ()
    plugin_path: str = "./plugins"
    config_by_plugin: Mapping[str, Mapping[str, object]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    lifecycle: PluginLifecyclePolicy = field(default_factory=PluginLifecyclePolicy)

    @property
    def requires_plugin_bootstrap(self) -> bool:
        """配置是否显式启用了插件控制面."""
        return self.enabled

    @property
    def local(self) -> LocalPluginSettings:
        """把 YAML 的扁平路径转换为发现层设置."""
        return LocalPluginSettings(path=self.plugin_path)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PluginSettings":
        raw_plugins = data.get("plugins", {})
        if not isinstance(raw_plugins, Mapping):
            raise ConfigError("配置项 'plugins' 应为映射")

        unknown = sorted(
            set(raw_plugins)
            - {"config", "enabled", "lifecycle", "plugin_list", "plugin_path"}
        )
        if unknown:
            raise ConfigError("配置项 'plugins' 包含未知字段: %s" % ", ".join(unknown))

        enabled = raw_plugins.get("enabled", False)
        if not isinstance(enabled, bool):
            raise ConfigError("配置项 'plugins.enabled' 应为布尔值")

        raw_plugin_list = raw_plugins.get("plugin_list", [])
        if not isinstance(raw_plugin_list, list):
            raise ConfigError("配置项 'plugins.plugin_list' 应为列表")

        plugin_list: list[str] = []
        for plugin_name in raw_plugin_list:
            plugin_list.append(
                _validate_config_plugin_name(plugin_name, "plugins.plugin_list")
            )
        if len(set(plugin_list)) != len(plugin_list):
            raise ConfigError("配置项 'plugins.plugin_list' 包含重复 plugin_name")

        plugin_path = raw_plugins.get("plugin_path", "./plugins")
        if (
            not isinstance(plugin_path, str)
            or not plugin_path
            or plugin_path != plugin_path.strip()
        ):
            raise ConfigError(
                "配置项 'plugins.plugin_path' 应为非空且无首尾空白的字符串"
            )
        config_by_plugin = _parse_plugin_config(raw_plugins.get("config", {}))
        return cls(
            enabled=enabled,
            plugin_list=tuple(plugin_list),
            plugin_path=plugin_path,
            config_by_plugin=config_by_plugin,
            lifecycle=_parse_lifecycle_policy(raw_plugins.get("lifecycle", {})),
        )


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


def _parse_lifecycle_policy(value: object) -> PluginLifecyclePolicy:
    if not isinstance(value, Mapping):
        raise ConfigError("配置项 'plugins.lifecycle' 应为映射")
    allowed = {
        "cleanup_timeout",
        "drain_timeout",
        "start_timeout",
        "stop_timeout",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigError(
            "配置项 'plugins.lifecycle' 包含未知字段: %s" % ", ".join(unknown)
        )
    return PluginLifecyclePolicy(
        start_timeout=value.get("start_timeout", 30.0),
        stop_timeout=value.get("stop_timeout", 10.0),
        cleanup_timeout=value.get("cleanup_timeout", 10.0),
        drain_timeout=value.get("drain_timeout", 5.0),
    )


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


def _validate_config_plugin_name(value: object, path: str) -> str:
    try:
        return validate_plugin_name(value)
    except PluginCompatibilityError as exc:
        raise ConfigError("%s 包含无效 plugin_name: %r" % (path, value)) from exc


__all__ = [
    "LocalPluginSettings",
    "PluginLifecyclePolicy",
    "PluginSettings",
]
