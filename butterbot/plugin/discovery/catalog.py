from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Any, Protocol

from butterbot import __version__
from butterbot.plugin.contracts.descriptor import PluginDescriptor
from butterbot.plugin.contracts.hooks import ButterPlugin
from butterbot.plugin.contracts.identifiers import validate_plugin_id
from butterbot.plugin.errors import (
    PluginCompatibilityError,
    PluginDependencyError,
    PluginDiscoveryError,
)

from .directory import (
    index_local_manifests,
    load_local_hooks,
    validate_distribution_requirements,
)
from .manifest import LocalPluginManifest
from .origin import (
    DirectoryPluginOrigin,
    DistributionPluginOrigin,
    PluginOrigin,
)
from .settings import LocalPluginSettings

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
    hooks: ButterPlugin
    origin: PluginOrigin

    @property
    def plugin(self) -> ButterPlugin:
        """兼容 P0 provisional API 的 hook 别名."""
        return self.hooks


CandidateLoader = Callable[[], LoadedPlugin]


@dataclass(frozen=True, slots=True)
class PluginCandidate:
    """尚未执行或已经静态描述的统一插件候选."""

    plugin_id: str
    origin: PluginOrigin
    _loader: CandidateLoader = field(repr=False, compare=False)
    descriptor: PluginDescriptor | None = None
    requires_distributions: tuple[str, ...] = ()

    def load(self) -> LoadedPlugin:
        return self._loader()


@dataclass(frozen=True, slots=True)
class PluginCatalog:
    """多来源候选以及已启用插件的确定性依赖顺序."""

    plugins: tuple[LoadedPlugin, ...]
    candidates: tuple[PluginCandidate, ...] = ()
    selected_ids: tuple[str, ...] = ()

    @property
    def plugin_ids(self) -> tuple[str, ...]:
        return tuple(item.descriptor.plugin_id for item in self.plugins)

    def get(self, plugin_id: str) -> LoadedPlugin | None:
        return next(
            (item for item in self.plugins if item.descriptor.plugin_id == plugin_id),
            None,
        )

    @classmethod
    def index_candidates(
        cls,
        *,
        entry_points: Iterable[PluginEntryPoint] | None = None,
        local: LocalPluginSettings | None = None,
        config_root: Path | None = None,
    ) -> tuple[PluginCandidate, ...]:
        """只索引 entry point 与本地 manifest，不导入插件代码."""
        available = tuple(
            metadata.entry_points(group=ENTRY_POINT_GROUP)
            if entry_points is None
            else entry_points
        )
        candidates = [_distribution_candidate(entry_point) for entry_point in available]
        if local is not None:
            root = (config_root or Path.cwd()).resolve()
            candidates.extend(
                _directory_candidate(manifest)
                for manifest in index_local_manifests(local, config_root=root)
            )
        ordered = tuple(
            sorted(
                candidates,
                key=lambda item: (
                    item.plugin_id,
                    item.origin.kind,
                    item.origin.location,
                ),
            )
        )
        _reject_origin_collisions(ordered)
        return ordered

    @classmethod
    def discover(
        cls,
        enabled: Iterable[str],
        *,
        entry_points: Iterable[PluginEntryPoint] | None = None,
        local: LocalPluginSettings | None = None,
        config_root: Path | None = None,
        core_version: str | None = None,
    ) -> "PluginCatalog":
        """统一选择并加载 entry point 和本地目录候选."""
        enabled_ids = tuple(enabled)
        if len(set(enabled_ids)) != len(enabled_ids):
            raise PluginDiscoveryError("plugins.enabled 包含重复 plugin ID")

        candidates = cls.index_candidates(
            entry_points=entry_points,
            local=local,
            config_root=config_root,
        )
        by_id = {candidate.plugin_id: candidate for candidate in candidates}
        selected = list(enabled_ids)
        if local is not None and local.auto_enable:
            selected.extend(
                candidate.plugin_id
                for candidate in candidates
                if isinstance(candidate.origin, DirectoryPluginOrigin)
                and candidate.plugin_id not in selected
            )
        selected_ids = tuple(selected)
        if not selected_ids:
            return cls((), candidates, ())

        for plugin_id in selected_ids:
            if plugin_id not in by_id:
                raise PluginDiscoveryError(
                    "已启用插件 '%s' 没有对应的 entry point 或本地 manifest" % plugin_id
                )

        loaded: dict[str, LoadedPlugin] = {}
        resolved_core_version = core_version or __version__
        for plugin_id in sorted(selected_ids):
            candidate = by_id[plugin_id]
            if candidate.requires_distributions:
                validate_distribution_requirements(
                    plugin_id,
                    candidate.requires_distributions,
                )
            item = candidate.load()
            descriptor = item.descriptor
            if descriptor.plugin_id != plugin_id:
                raise PluginDiscoveryError(
                    "候选 '%s' 返回的 plugin_id 是 '%s'"
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
            loaded[plugin_id] = item

        _validate_dependencies(loaded)
        _validate_capabilities(loaded)
        ordered_ids = _topological_order(loaded)
        return cls(
            tuple(loaded[plugin_id] for plugin_id in ordered_ids),
            candidates,
            selected_ids,
        )


def _distribution_candidate(entry_point: PluginEntryPoint) -> PluginCandidate:
    try:
        plugin_id = validate_plugin_id(entry_point.name)
    except PluginCompatibilityError as exc:
        raise PluginDiscoveryError(
            "entry point plugin ID 无效: %s" % entry_point.name
        ) from exc
    distribution = getattr(entry_point, "dist", None)
    distribution_name = getattr(distribution, "name", None)
    origin = DistributionPluginOrigin(
        distribution=distribution_name,
        entry_point_group=ENTRY_POINT_GROUP,
        entry_point_name=entry_point.name,
        entry_point_value=entry_point.value,
    )

    def load() -> LoadedPlugin:
        plugin, descriptor = _load_distribution_plugin(entry_point)
        return LoadedPlugin(descriptor, plugin, origin)

    return PluginCandidate(
        plugin_id=plugin_id,
        origin=origin,
        _loader=load,
    )


def _directory_candidate(manifest: LocalPluginManifest) -> PluginCandidate:
    def load() -> LoadedPlugin:
        hooks = load_local_hooks(manifest)
        return LoadedPlugin(manifest.descriptor, hooks, manifest.origin)

    return PluginCandidate(
        plugin_id=manifest.plugin_id,
        origin=manifest.origin,
        descriptor=manifest.descriptor,
        requires_distributions=manifest.requires_distributions,
        _loader=load,
    )


def _reject_origin_collisions(candidates: tuple[PluginCandidate, ...]) -> None:
    grouped: dict[str, list[PluginCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.plugin_id].append(candidate)
    for plugin_id, matches in sorted(grouped.items()):
        if len(matches) < 2:
            continue
        origins = ", ".join(
            "%s:%s" % (candidate.origin.kind, candidate.origin.location)
            for candidate in matches
        )
        label = (
            "重复 entry point 来源"
            if all(
                isinstance(candidate.origin, DistributionPluginOrigin)
                for candidate in matches
            )
            else "重复来源"
        )
        raise PluginDiscoveryError("插件 '%s' 有%s: %s" % (plugin_id, label, origins))


def _load_distribution_plugin(
    entry_point: PluginEntryPoint,
) -> tuple[ButterPlugin, PluginDescriptor]:
    try:
        target = entry_point.load()
        candidate = (
            target
            if _looks_like_distribution_plugin(target) and not inspect.isclass(target)
            else target()
            if callable(target)
            else None
        )
    except Exception as exc:
        raise PluginDiscoveryError(
            "导入插件 '%s' 失败（%s）" % (entry_point.name, type(exc).__name__)
        ) from exc

    if candidate is None or not _looks_like_distribution_plugin(candidate):
        if inspect.iscoroutine(candidate):
            candidate.close()
        raise PluginDiscoveryError(
            "插件 entry point '%s' 必须返回 ButterPlugin 实例或零参数 factory"
            % entry_point.name
        )
    assert isinstance(candidate, ButterPlugin)
    descriptor = getattr(candidate, "descriptor", None)
    if not isinstance(descriptor, PluginDescriptor):
        raise PluginDiscoveryError(
            "插件 '%s' 的 descriptor 必须是 PluginDescriptor" % entry_point.name
        )
    return candidate, descriptor


def _looks_like_distribution_plugin(candidate: object) -> bool:
    return (
        isinstance(candidate, ButterPlugin)
        and hasattr(candidate, "descriptor")
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
    "PluginCandidate",
    "PluginCatalog",
    "PluginEntryPoint",
]
