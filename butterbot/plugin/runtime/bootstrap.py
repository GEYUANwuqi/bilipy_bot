"""由 BotApp 按最终配置动态导入的插件运行时工厂."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from butterbot.core.exceptions import ConfigError
from butterbot.plugin.discovery.catalog import PluginCatalog
from butterbot.plugin.discovery.settings import PluginSettings

from .manager import PluginManager

if TYPE_CHECKING:
    from butterbot.app.bot_app import BotApp
    from butterbot.app.config import RuntimeConfig


def create_optional_runtime(app: "BotApp", config: "RuntimeConfig") -> PluginManager:
    """发现最终配置选中的插件并绑定到应用，不创建 Source."""
    settings = PluginSettings.from_mapping(
        {"plugins": _thaw_mapping(config.plugin_config)}
    )
    if not settings.enabled:
        raise ConfigError("插件运行时只能在 plugins.enabled=true 时创建")

    catalog = PluginCatalog.discover(
        settings.plugin_list,
        local=settings.local,
        config_root=config.config_root,
    )
    configured_ids = set(settings.config_by_plugin)
    enabled_ids = set(catalog.plugin_ids)
    unknown = sorted(configured_ids - enabled_ids)
    if unknown:
        raise ConfigError(
            "plugins.config 引用了未启用的 plugin ID: %s" % ", ".join(unknown)
        )

    manager = PluginManager(
        catalog,
        plugin_settings=settings.config_by_plugin,
        lifecycle=settings.lifecycle,
    )
    manager.bind(app)
    return manager


def _thaw_mapping(value: Mapping[str, object]) -> dict[str, Any]:
    return {key: _thaw(item) for key, item in value.items()}


def _thaw(value: object) -> Any:
    if isinstance(value, Mapping):
        return _thaw_mapping(value)
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return [_thaw(item) for item in value]
    return value


__all__ = ["create_optional_runtime"]
