"""ButterBot 插件作者使用的稳定 API."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from butterbot.plugin.contracts import (
    ButterPlugin,
    PluginConfig,
    PluginContext,
    PluginDescriptor,
    PluginScope,
    SourceRef,
    configure,
    register,
)

from .errors import (
    PluginCompatibilityError,
    PluginDependencyError,
    PluginDiscoveryError,
    PluginError,
    PluginRegistrationError,
)

if TYPE_CHECKING:
    from butterbot.plugin.runtime.registrar import ConfigRegistrar

_LAZY_EXPORTS = {
    "ConfigRegistrar": ("butterbot.plugin.runtime.registrar", "ConfigRegistrar"),
}


def __getattr__(name: str) -> Any:
    """延迟导入作者配置阶段所需的 registrar 类型."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))


__all__ = [
    "ButterPlugin",
    "ConfigRegistrar",
    "PluginCompatibilityError",
    "PluginConfig",
    "PluginContext",
    "PluginDependencyError",
    "PluginDescriptor",
    "PluginDiscoveryError",
    "PluginError",
    "PluginRegistrationError",
    "PluginScope",
    "SourceRef",
    "configure",
    "register",
]
