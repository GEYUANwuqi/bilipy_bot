from __future__ import annotations

from dataclasses import dataclass

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from butterbot.plugin.errors import PluginCompatibilityError

from .identifiers import (
    CAPABILITY_PATTERN,
    PLUGIN_ID_PATTERN,
    validate_identifier,
    validate_unique_identifiers,
)

_DESCRIPTOR_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class PluginDescriptor:
    """插件的最小身份、兼容和依赖描述."""

    plugin_id: str
    version: str
    requires_core: str
    requires_plugins: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    schema_version: int = _DESCRIPTOR_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != _DESCRIPTOR_SCHEMA_VERSION:
            raise PluginCompatibilityError(
                "插件 '%s' 使用不支持的 descriptor schema %r"
                % (self.plugin_id, self.schema_version)
            )
        validate_identifier(self.plugin_id, "plugin_id", PLUGIN_ID_PATTERN)
        try:
            Version(self.version)
        except InvalidVersion as exc:
            raise PluginCompatibilityError(
                "插件 '%s' 的版本无效: %s" % (self.plugin_id, self.version)
            ) from exc
        try:
            SpecifierSet(self.requires_core)
        except InvalidSpecifier as exc:
            raise PluginCompatibilityError(
                "插件 '%s' 的核心版本约束无效: %s"
                % (self.plugin_id, self.requires_core)
            ) from exc

        validate_unique_identifiers(
            self.requires_plugins,
            "requires_plugins",
            PLUGIN_ID_PATTERN,
        )
        if self.plugin_id in self.requires_plugins:
            raise PluginCompatibilityError("插件 '%s' 不能依赖自身" % self.plugin_id)
        validate_unique_identifiers(
            self.provides,
            "provides",
            CAPABILITY_PATTERN,
        )

    def supports_core(self, core_version: str) -> bool:
        """当前核心版本是否满足描述中的约束."""
        try:
            parsed_version = Version(core_version)
        except InvalidVersion as exc:
            raise PluginCompatibilityError(
                "ButterBot 核心版本无效: %s" % core_version
            ) from exc
        return SpecifierSet(self.requires_core).contains(
            parsed_version,
            prereleases=True,
        )


__all__ = ["PluginDescriptor"]
