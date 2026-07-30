from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from .errors import PluginCompatibilityError

if TYPE_CHECKING:
    from .registrar import ConfigRegistrar, PluginRegistrar

_PLUGIN_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")
_CAPABILITY_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]*[a-z0-9])?$")
_DESCRIPTOR_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class PluginDescriptor:
    """实验插件的最小身份、兼容和依赖描述."""

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
        _validate_identifier(self.plugin_id, "plugin_id", _PLUGIN_ID_PATTERN)
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

        _validate_unique_identifiers(
            self.requires_plugins,
            "requires_plugins",
            _PLUGIN_ID_PATTERN,
        )
        if self.plugin_id in self.requires_plugins:
            raise PluginCompatibilityError("插件 '%s' 不能依赖自身" % self.plugin_id)
        _validate_unique_identifiers(
            self.provides,
            "provides",
            _CAPABILITY_PATTERN,
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


@runtime_checkable
class Plugin(Protocol):
    """可信、启动期实验插件协议."""

    descriptor: PluginDescriptor

    def register_config(self, registrar: "ConfigRegistrar") -> None:
        """登记配置 builder 和 Source factory，不产生运行时任务."""

    async def register(self, registrar: "PluginRegistrar") -> None:
        """登记 Source、Handler 和清理回调."""


class PluginBase:
    """为只实现一个阶段的插件提供空 hook."""

    descriptor: PluginDescriptor

    def register_config(self, registrar: "ConfigRegistrar") -> None:
        del registrar

    async def register(self, registrar: "PluginRegistrar") -> None:
        del registrar


def _validate_identifier(
    value: object,
    label: str,
    pattern: re.Pattern[str],
) -> None:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise PluginCompatibilityError(
            "%s 必须使用小写字母、数字及 '.', '_' 或 '-' 组成的稳定标识" % label
        )


def _validate_unique_identifiers(
    values: object,
    label: str,
    pattern: re.Pattern[str],
) -> None:
    if not isinstance(values, tuple):
        raise PluginCompatibilityError("%s 必须是 tuple" % label)
    seen: set[str] = set()
    for value in values:
        _validate_identifier(value, label, pattern)
        if value in seen:
            raise PluginCompatibilityError("%s 包含重复标识 '%s'" % (label, value))
        seen.add(value)


__all__ = [
    "Plugin",
    "PluginBase",
    "PluginDescriptor",
]
