from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import metadata
from typing import Any, Protocol, cast

from butterbot import __version__

from .descriptor import Plugin, PluginDescriptor
from .errors import (
    PluginCompatibilityError,
    PluginDependencyError,
    PluginDiscoveryError,
)

ENTRY_POINT_GROUP = "butterbot.plugins"


class PluginEntryPoint(Protocol):
    """发现层所需的最小 entry point 接口，便于隔离测试."""

    name: str
    value: str

    def load(self) -> Any: ...


@dataclass(frozen=True, slots=True)
class LoadedPlugin:
    """一个已导入并通过静态校验的插件."""

    descriptor: PluginDescriptor
    plugin: Plugin
    entry_point: PluginEntryPoint


@dataclass(frozen=True, slots=True)
class PluginCatalog:
    """已启用插件的确定性依赖顺序."""

    plugins: tuple[LoadedPlugin, ...]

    @property
    def plugin_ids(self) -> tuple[str, ...]:
        return tuple(item.descriptor.plugin_id for item in self.plugins)

    def get(self, plugin_id: str) -> LoadedPlugin | None:
        return next(
            (item for item in self.plugins if item.descriptor.plugin_id == plugin_id),
            None,
        )

    @classmethod
    def discover(
        cls,
        enabled: Iterable[str],
        *,
        entry_points: Iterable[PluginEntryPoint] | None = None,
        core_version: str | None = None,
    ) -> "PluginCatalog":
        """只导入显式启用的 entry point，并按依赖拓扑排序."""
        enabled_ids = tuple(enabled)
        if len(set(enabled_ids)) != len(enabled_ids):
            raise PluginDiscoveryError("plugins.enabled 包含重复 plugin ID")
        if not enabled_ids:
            return cls(())

        available = tuple(
            metadata.entry_points(group=ENTRY_POINT_GROUP)
            if entry_points is None
            else entry_points
        )
        by_name: dict[str, list[PluginEntryPoint]] = defaultdict(list)
        for entry_point in available:
            by_name[entry_point.name].append(entry_point)

        loaded: dict[str, LoadedPlugin] = {}
        resolved_core_version = core_version or __version__
        for plugin_id in sorted(enabled_ids):
            matches = by_name.get(plugin_id, [])
            if not matches:
                raise PluginDiscoveryError(
                    "已启用插件 '%s' 没有对应的 %s entry point"
                    % (plugin_id, ENTRY_POINT_GROUP)
                )
            if len(matches) > 1:
                values = sorted(entry.value for entry in matches)
                raise PluginDiscoveryError(
                    "插件 '%s' 有重复 entry point: %s" % (plugin_id, ", ".join(values))
                )

            entry_point = matches[0]
            plugin = _load_plugin(entry_point)
            descriptor = plugin.descriptor
            if descriptor.plugin_id != plugin_id:
                raise PluginDiscoveryError(
                    "entry point '%s' 返回的 plugin_id 是 '%s'"
                    % (plugin_id, descriptor.plugin_id)
                )
            if not descriptor.supports_core(resolved_core_version):
                raise PluginCompatibilityError(
                    "插件 '%s' 要求 ButterBot %s，当前为 %s"
                    % (
                        plugin_id,
                        descriptor.requires_core,
                        resolved_core_version,
                    )
                )
            loaded[plugin_id] = LoadedPlugin(
                descriptor=descriptor,
                plugin=plugin,
                entry_point=entry_point,
            )

        _validate_dependencies(loaded)
        _validate_capabilities(loaded)
        ordered_ids = _topological_order(loaded)
        return cls(tuple(loaded[plugin_id] for plugin_id in ordered_ids))


def _load_plugin(entry_point: PluginEntryPoint) -> Plugin:
    try:
        target = entry_point.load()
        candidate = (
            target
            if _looks_like_plugin(target) and not inspect.isclass(target)
            else target()
            if callable(target)
            else None
        )
    except Exception as exc:
        raise PluginDiscoveryError(
            "导入插件 '%s' 失败（%s）" % (entry_point.name, type(exc).__name__)
        ) from exc

    if candidate is None or not _looks_like_plugin(candidate):
        raise PluginDiscoveryError(
            "插件 entry point '%s' 必须返回 Plugin 实例或零参数 factory"
            % entry_point.name
        )
    plugin = cast(Plugin, candidate)
    if not isinstance(plugin.descriptor, PluginDescriptor):
        raise PluginDiscoveryError(
            "插件 '%s' 的 descriptor 必须是 PluginDescriptor" % entry_point.name
        )
    return plugin


def _looks_like_plugin(candidate: object) -> bool:
    return (
        hasattr(candidate, "descriptor")
        and callable(getattr(candidate, "register_config", None))
        and callable(getattr(candidate, "register", None))
    )


def _validate_dependencies(loaded: dict[str, LoadedPlugin]) -> None:
    enabled = set(loaded)
    for plugin_id, item in loaded.items():
        missing = sorted(set(item.descriptor.requires_plugins) - enabled)
        if missing:
            raise PluginDependencyError(
                "插件 '%s' 缺少已启用依赖: %s" % (plugin_id, ", ".join(missing))
            )


def _validate_capabilities(loaded: dict[str, LoadedPlugin]) -> None:
    owners: dict[str, str] = {}
    for plugin_id in sorted(loaded):
        for capability in loaded[plugin_id].descriptor.provides:
            previous = owners.get(capability)
            if previous is not None:
                raise PluginCompatibilityError(
                    "能力 '%s' 同时由插件 '%s' 和 '%s' 提供"
                    % (capability, previous, plugin_id)
                )
            owners[capability] = plugin_id


def _topological_order(loaded: dict[str, LoadedPlugin]) -> tuple[str, ...]:
    ordered: list[str] = []
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(plugin_id: str) -> None:
        if plugin_id in visited:
            return
        if plugin_id in visiting:
            cycle_start = visiting.index(plugin_id)
            cycle = visiting[cycle_start:] + [plugin_id]
            raise PluginDependencyError("插件依赖循环: %s" % " -> ".join(cycle))

        visiting.append(plugin_id)
        for dependency in sorted(loaded[plugin_id].descriptor.requires_plugins):
            visit(dependency)
        visiting.pop()
        visited.add(plugin_id)
        ordered.append(plugin_id)

    for plugin_id in sorted(loaded):
        visit(plugin_id)
    return tuple(ordered)


EntryPointProvider = Callable[[], Iterable[PluginEntryPoint]]

__all__ = [
    "ENTRY_POINT_GROUP",
    "LoadedPlugin",
    "PluginCatalog",
    "PluginEntryPoint",
]
