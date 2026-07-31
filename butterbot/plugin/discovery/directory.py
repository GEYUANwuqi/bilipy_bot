from __future__ import annotations

import hashlib
import importlib.util
import inspect
import sys
from collections.abc import Iterable
from importlib import metadata
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType

from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version

from butterbot.plugin.contracts.hooks import ButterPlugin
from butterbot.plugin.errors import PluginDependencyError, PluginDiscoveryError

from .manifest import LocalPluginManifest
from .settings import LocalPluginSettings

_LOCAL_NAMESPACE = "_butterbot_local"


def index_local_manifests(
    settings: LocalPluginSettings,
    *,
    config_root: Path,
) -> tuple[LocalPluginManifest, ...]:
    """确定性扫描直接子目录，只读取 manifest 和入口字节."""
    configured_root = Path(settings.path)
    plugin_root = (
        configured_root
        if configured_root.is_absolute()
        else config_root / configured_root
    )
    if plugin_root.is_symlink():
        raise PluginDiscoveryError("本地插件根目录不允许是符号链接: %s" % plugin_root)
    if not plugin_root.exists():
        if settings.auto_enable:
            raise PluginDiscoveryError(
                "本地插件根目录不存在，无法自动启用: %s" % plugin_root
            )
        return ()
    if not plugin_root.is_dir():
        raise PluginDiscoveryError("本地插件根路径必须是目录: %s" % plugin_root)

    try:
        children = sorted(plugin_root.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        raise PluginDiscoveryError(
            "无法扫描本地插件根目录 '%s'（%s）" % (plugin_root, type(exc).__name__)
        ) from exc

    manifests: list[LocalPluginManifest] = []
    for child in children:
        if child.name.startswith(".") or child.name == "__pycache__":
            continue
        if child.is_symlink():
            raise PluginDiscoveryError("本地插件候选不允许是符号链接: %s" % child)
        manifest_path = child / "plugin.toml"
        if not child.is_dir() or not (
            manifest_path.exists() or manifest_path.is_symlink()
        ):
            continue
        manifests.append(LocalPluginManifest.from_directory(child))
    return tuple(manifests)


def validate_distribution_requirements(
    plugin_id: str,
    requirements: Iterable[str],
) -> None:
    """在 import 本地插件前检查声明的 distribution，不修改环境."""
    for requirement_text in requirements:
        requirement = Requirement(requirement_text)
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        try:
            installed = metadata.version(requirement.name)
        except metadata.PackageNotFoundError as exc:
            raise PluginDependencyError(
                "本地插件 '%s' 缺少 Python distribution: %s" % (plugin_id, requirement)
            ) from exc
        try:
            installed_version = Version(installed)
        except InvalidVersion as exc:
            raise PluginDependencyError(
                "本地插件 '%s' 的 Python distribution '%s' 版本无效: %s"
                % (plugin_id, requirement.name, installed)
            ) from exc
        if requirement.specifier and not requirement.specifier.contains(
            installed_version,
            prereleases=True,
        ):
            raise PluginDependencyError(
                "本地插件 '%s' 要求 Python distribution %s，当前为 %s"
                % (plugin_id, requirement, installed)
            )


def load_local_plugin(manifest: LocalPluginManifest) -> ButterPlugin:
    """在私有合成 package 中加载一个显式启用的本地插件入口."""
    origin = manifest.origin
    namespace_hash = hashlib.sha256(
        ("%s\0%s" % (origin.plugin_root, manifest.plugin_id)).encode()
    ).hexdigest()[:20]
    package_name = "%s.p_%s" % (_LOCAL_NAMESPACE, namespace_hash)
    module_name = "%s.%s" % (package_name, origin.entry_path.stem)
    created: set[str] = set()

    try:
        _ensure_namespace(_LOCAL_NAMESPACE, (), created)
        _ensure_namespace(package_name, (str(origin.plugin_root),), created)
        spec = importlib.util.spec_from_file_location(module_name, origin.entry_path)
        if spec is None or spec.loader is None:
            raise PluginDiscoveryError(
                "无法创建本地插件入口模块: %s" % origin.entry_path
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        created.add(module_name)
        spec.loader.exec_module(module)
        plugin_class = _find_local_plugin_class(module, manifest.plugin_id)
        candidate = plugin_class()
        if not isinstance(candidate, ButterPlugin):
            raise PluginDiscoveryError(
                "本地插件 '%s' 自动实例化后不是 ButterPlugin" % manifest.plugin_id
            )
        return candidate
    except BaseException as exc:
        _remove_namespace(package_name)
        for name in sorted(created, reverse=True):
            if name == _LOCAL_NAMESPACE and _has_namespace_children(name):
                continue
            sys.modules.pop(name, None)
        if isinstance(exc, PluginDiscoveryError):
            raise
        if not isinstance(exc, Exception):
            raise
        raise PluginDiscoveryError(
            "导入本地插件 '%s' 失败（%s）" % (manifest.plugin_id, type(exc).__name__)
        ) from exc


def _ensure_namespace(
    name: str,
    search_locations: tuple[str, ...],
    created: set[str],
) -> None:
    existing = sys.modules.get(name)
    if existing is not None:
        if (
            search_locations
            and tuple(getattr(existing, "__path__", ())) != search_locations
        ):
            raise PluginDiscoveryError("本地插件内部模块命名空间冲突: %s" % name)
        return
    module = ModuleType(name)
    spec = ModuleSpec(name, loader=None, is_package=True)
    spec.submodule_search_locations = list(search_locations)
    module.__spec__ = spec
    module.__package__ = name
    module.__path__ = list(search_locations)
    sys.modules[name] = module
    created.add(name)


def _find_local_plugin_class(
    module: ModuleType,
    plugin_id: str,
) -> type[ButterPlugin]:
    candidates = {
        candidate
        for candidate in vars(module).values()
        if inspect.isclass(candidate)
        and candidate is not ButterPlugin
        and issubclass(candidate, ButterPlugin)
        and candidate.__module__ == module.__name__
        and not inspect.isabstract(candidate)
    }
    if len(candidates) != 1:
        names = ", ".join(sorted(candidate.__qualname__ for candidate in candidates))
        raise PluginDiscoveryError(
            "本地插件 '%s' 的 entry 模块必须且只能定义一个 ButterPlugin 子类；找到: %s"
            % (plugin_id, names or "0")
        )
    return candidates.pop()


def _remove_namespace(package_name: str) -> None:
    for name in tuple(sys.modules):
        if name == package_name or name.startswith(package_name + "."):
            sys.modules.pop(name, None)


def _has_namespace_children(name: str) -> bool:
    return any(candidate.startswith(name + ".") for candidate in sys.modules)


__all__ = [
    "index_local_manifests",
    "load_local_plugin",
    "validate_distribution_requirements",
]
