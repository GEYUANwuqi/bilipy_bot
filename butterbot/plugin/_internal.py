"""框架自身使用的插件发现与运行时控制面."""

from butterbot.plugin.contracts import SubscriptionSpec
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
    PluginRegistrar,
    RegistrationReceipt,
)

__all__ = [
    "CleanupRegistration",
    "DirectoryPluginOrigin",
    "DistributionPluginOrigin",
    "ENTRY_POINT_GROUP",
    "ExtensionRegistrar",
    "LocalPluginManifest",
    "LocalPluginSettings",
    "PluginBootstrap",
    "PluginCandidate",
    "PluginCatalog",
    "PluginFailure",
    "PluginFailurePhase",
    "PluginLifecyclePolicy",
    "PluginManager",
    "PluginOrigin",
    "PluginRegistrar",
    "PluginSettings",
    "PluginState",
    "PluginStatus",
    "RegistrationReceipt",
    "SubscriptionSpec",
    "bootstrap_app",
    "validate_plugin_config",
]
