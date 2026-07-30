"""插件候选发现、静态校验与目录加载."""

from .catalog import ENTRY_POINT_GROUP, PluginCandidate, PluginCatalog
from .manifest import LocalPluginManifest
from .origin import (
    DirectoryPluginOrigin,
    DistributionPluginOrigin,
    PluginOrigin,
)
from .settings import LocalPluginSettings, PluginSettings

__all__ = [
    "DirectoryPluginOrigin",
    "DistributionPluginOrigin",
    "ENTRY_POINT_GROUP",
    "LocalPluginManifest",
    "LocalPluginSettings",
    "PluginCandidate",
    "PluginCatalog",
    "PluginOrigin",
    "PluginSettings",
]
