"""ButterBot 插件作者使用的公开 API.

普通业务插件应只从这个包导入框架契约。事件源适配实现仍从
``butterbot.core`` 导入 ``BaseSource``、数据模型和事件类型基类。
"""

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
    SubscriptionSpec,
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
    from butterbot.plugin.discovery import (
        DirectoryPluginOrigin,
        DistributionPluginOrigin,
        LocalPluginManifest,
        LocalPluginSettings,
        PluginCandidate,
        PluginCatalog,
        PluginLifecyclePolicy,
        PluginOrigin,
        PluginSettings,
    )
    from butterbot.plugin.discovery.catalog import ENTRY_POINT_GROUP
    from butterbot.plugin.runtime.bootstrap import (
        PluginBootstrap,
        bootstrap_app,
        validate_plugin_config,
    )
    from butterbot.plugin.runtime.extension import ExtensionRegistrar
    from butterbot.plugin.runtime.manager import (
        PluginFailure,
        PluginFailurePhase,
        PluginManager,
        PluginState,
        PluginStatus,
    )
    from butterbot.plugin.runtime.registrar import (
        CleanupRegistration,
        ConfigRegistrar,
        PluginRegistrar,
        RegistrationReceipt,
    )

_LAZY_EXPORTS = {
    "CleanupRegistration": (
        "butterbot.plugin.runtime.registrar",
        "CleanupRegistration",
    ),
    "ConfigRegistrar": ("butterbot.plugin.runtime.registrar", "ConfigRegistrar"),
    "DirectoryPluginOrigin": (
        "butterbot.plugin.discovery.origin",
        "DirectoryPluginOrigin",
    ),
    "DistributionPluginOrigin": (
        "butterbot.plugin.discovery.origin",
        "DistributionPluginOrigin",
    ),
    "ENTRY_POINT_GROUP": ("butterbot.plugin.discovery.catalog", "ENTRY_POINT_GROUP"),
    "ExtensionRegistrar": (
        "butterbot.plugin.runtime.extension",
        "ExtensionRegistrar",
    ),
    "LocalPluginManifest": (
        "butterbot.plugin.discovery.manifest",
        "LocalPluginManifest",
    ),
    "LocalPluginSettings": (
        "butterbot.plugin.discovery.settings",
        "LocalPluginSettings",
    ),
    "PluginBootstrap": ("butterbot.plugin.runtime.bootstrap", "PluginBootstrap"),
    "PluginCandidate": ("butterbot.plugin.discovery.catalog", "PluginCandidate"),
    "PluginCatalog": ("butterbot.plugin.discovery.catalog", "PluginCatalog"),
    "PluginManager": ("butterbot.plugin.runtime.manager", "PluginManager"),
    "PluginFailure": ("butterbot.plugin.runtime.manager", "PluginFailure"),
    "PluginFailurePhase": (
        "butterbot.plugin.runtime.manager",
        "PluginFailurePhase",
    ),
    "PluginLifecyclePolicy": (
        "butterbot.plugin.discovery.settings",
        "PluginLifecyclePolicy",
    ),
    "PluginOrigin": ("butterbot.plugin.discovery.origin", "PluginOrigin"),
    "PluginRegistrar": ("butterbot.plugin.runtime.registrar", "PluginRegistrar"),
    "PluginSettings": ("butterbot.plugin.discovery.settings", "PluginSettings"),
    "PluginState": ("butterbot.plugin.runtime.manager", "PluginState"),
    "PluginStatus": ("butterbot.plugin.runtime.manager", "PluginStatus"),
    "RegistrationReceipt": (
        "butterbot.plugin.runtime.registrar",
        "RegistrationReceipt",
    ),
    "bootstrap_app": ("butterbot.plugin.runtime.bootstrap", "bootstrap_app"),
    "validate_plugin_config": (
        "butterbot.plugin.runtime.bootstrap",
        "validate_plugin_config",
    ),
}


def __getattr__(name: str) -> Any:
    """延迟导入发现与运行时控制面，保持插件契约轻量."""
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
    "CleanupRegistration",
    "ConfigRegistrar",
    "DirectoryPluginOrigin",
    "DistributionPluginOrigin",
    "ENTRY_POINT_GROUP",
    "ExtensionRegistrar",
    "LocalPluginManifest",
    "LocalPluginSettings",
    "PluginBootstrap",
    "PluginCandidate",
    "PluginCatalog",
    "PluginCompatibilityError",
    "PluginConfig",
    "PluginContext",
    "PluginDependencyError",
    "PluginDescriptor",
    "PluginDiscoveryError",
    "PluginError",
    "PluginFailure",
    "PluginFailurePhase",
    "PluginLifecyclePolicy",
    "PluginManager",
    "PluginOrigin",
    "PluginRegistrar",
    "PluginRegistrationError",
    "PluginScope",
    "PluginSettings",
    "PluginState",
    "PluginStatus",
    "RegistrationReceipt",
    "SourceRef",
    "SubscriptionSpec",
    "bootstrap_app",
    "configure",
    "register",
    "validate_plugin_config",
]
