"""可信、显式启用、启动期加载的 provisional 插件 API.

该命名空间在 3.x 中允许破坏性调整，不构成不可信 Python 代码沙箱，也不提供
运行期 install、reload 或 unload。
"""

from .bootstrap import (
    BotAppFactory,
    PluginBootstrap,
    bootstrap_app,
    validate_plugin_config,
)
from .descriptor import Plugin, PluginBase, PluginDescriptor
from .discovery import ENTRY_POINT_GROUP, PluginCatalog
from .errors import (
    PluginCompatibilityError,
    PluginDependencyError,
    PluginDiscoveryError,
    PluginError,
    PluginRegistrationError,
)
from .manager import PluginManager, PluginState, PluginStatus
from .registrar import (
    CleanupRegistration,
    ConfigRegistrar,
    PluginRegistrar,
    RegistrationReceipt,
    SubscriptionSpec,
)
from .settings import PluginSettings

__all__ = [
    "BotAppFactory",
    "CleanupRegistration",
    "ConfigRegistrar",
    "ENTRY_POINT_GROUP",
    "Plugin",
    "PluginBase",
    "PluginBootstrap",
    "PluginCatalog",
    "PluginCompatibilityError",
    "PluginDependencyError",
    "PluginDescriptor",
    "PluginDiscoveryError",
    "PluginError",
    "PluginManager",
    "PluginRegistrar",
    "PluginRegistrationError",
    "PluginSettings",
    "PluginState",
    "PluginStatus",
    "RegistrationReceipt",
    "SubscriptionSpec",
    "bootstrap_app",
    "validate_plugin_config",
]
