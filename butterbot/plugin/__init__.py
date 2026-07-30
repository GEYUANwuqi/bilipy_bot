"""ButterBot 插件作者使用的公开 API.

普通业务插件应只从这个包导入框架契约。事件源适配实现仍从
``butterbot.core`` 导入 ``BaseSource``、数据模型和事件类型基类。
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from butterbot.core.event import Event
from butterbot.core.filter import AndFilter, BaseFilter, OrFilter
from butterbot.core.types import BaseType

from .descriptor import (
    LocalPlugin,
    Plugin,
    PluginBase,
    PluginDescriptor,
    PluginHooks,
    validate_plugin_id,
)
from .discovery import ENTRY_POINT_GROUP, PluginCandidate, PluginCatalog
from .errors import (
    PluginCompatibilityError,
    PluginDependencyError,
    PluginDiscoveryError,
    PluginError,
    PluginRegistrationError,
)
from .extension import ExtensionRegistrar, SubscriptionSpec
from .manager import PluginManager, PluginState, PluginStatus
from .manifest import LocalPluginManifest
from .origin import (
    DirectoryPluginOrigin,
    DistributionPluginOrigin,
    PluginOrigin,
)
from .registrar import (
    CleanupRegistration,
    ConfigRegistrar,
    PluginRegistrar,
    RegistrationReceipt,
)
from .settings import LocalPluginSettings, PluginSettings
from .source_ref import SourceRef

if TYPE_CHECKING:
    from .bootstrap import (
        BotAppFactory,
        PluginBootstrap,
        bootstrap_app,
        validate_plugin_config,
    )

_BOOTSTRAP_EXPORTS = frozenset(
    {
        "BotAppFactory",
        "PluginBootstrap",
        "bootstrap_app",
        "validate_plugin_config",
    }
)


def __getattr__(name: str) -> Any:
    """延迟导入依赖 BotApp 的 bootstrap，避免应用入口循环导入."""
    if name not in _BOOTSTRAP_EXPORTS:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    value = getattr(import_module(".bootstrap", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | _BOOTSTRAP_EXPORTS)


__all__ = [
    "AndFilter",
    "BaseFilter",
    "BaseType",
    "BotAppFactory",
    "CleanupRegistration",
    "ConfigRegistrar",
    "DirectoryPluginOrigin",
    "DistributionPluginOrigin",
    "ENTRY_POINT_GROUP",
    "Event",
    "ExtensionRegistrar",
    "LocalPlugin",
    "LocalPluginManifest",
    "LocalPluginSettings",
    "OrFilter",
    "Plugin",
    "PluginBase",
    "PluginBootstrap",
    "PluginCandidate",
    "PluginCatalog",
    "PluginCompatibilityError",
    "PluginDependencyError",
    "PluginDescriptor",
    "PluginDiscoveryError",
    "PluginError",
    "PluginHooks",
    "PluginManager",
    "PluginOrigin",
    "PluginRegistrar",
    "PluginRegistrationError",
    "PluginSettings",
    "PluginState",
    "PluginStatus",
    "RegistrationReceipt",
    "SourceRef",
    "SubscriptionSpec",
    "bootstrap_app",
    "validate_plugin_config",
    "validate_plugin_id",
]
