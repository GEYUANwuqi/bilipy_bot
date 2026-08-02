"""ButterBot 插件作者使用的稳定 API."""

from __future__ import annotations

from butterbot.plugin.contracts import (
    ButterPlugin,
    PluginConfig,
    PluginContext,
    PluginDescriptor,
    PluginScope,
    SourceRef,
    register,
)

from .errors import (
    PluginCompatibilityError,
    PluginDependencyError,
    PluginDiscoveryError,
    PluginError,
    PluginRegistrationError,
)

__all__ = [
    "ButterPlugin",
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
    "register",
]
