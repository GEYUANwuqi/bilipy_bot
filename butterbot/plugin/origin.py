from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class DistributionPluginOrigin:
    """由已安装 distribution entry point 提供的插件来源."""

    distribution: str | None
    entry_point_group: str
    entry_point_name: str
    entry_point_value: str

    @property
    def kind(self) -> str:
        return "distribution"

    @property
    def location(self) -> str:
        distribution = self.distribution or "<unknown distribution>"
        return "%s:%s=%s" % (
            distribution,
            self.entry_point_name,
            self.entry_point_value,
        )

    @property
    def resource_root(self) -> None:
        return None

    @property
    def fingerprint(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class DirectoryPluginOrigin:
    """由工作区本地目录 manifest 提供的插件来源."""

    plugin_root: Path
    manifest_path: Path
    entry_path: Path
    fingerprint: str

    @property
    def kind(self) -> str:
        return "directory"

    @property
    def location(self) -> str:
        return str(self.plugin_root)

    @property
    def resource_root(self) -> Path:
        return self.plugin_root


PluginOrigin: TypeAlias = DistributionPluginOrigin | DirectoryPluginOrigin


__all__ = [
    "DirectoryPluginOrigin",
    "DistributionPluginOrigin",
    "PluginOrigin",
]
