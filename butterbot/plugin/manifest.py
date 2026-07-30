from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement

from .descriptor import PluginDescriptor
from .errors import PluginCompatibilityError, PluginDiscoveryError
from .origin import DirectoryPluginOrigin

_MANIFEST_NAME = "plugin.toml"
_ENTRY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.py$")
_REQUIRED_FIELDS = {
    "schema_version",
    "plugin_id",
    "version",
    "requires_core",
    "entry",
}
_OPTIONAL_FIELDS = {
    "requires_plugins",
    "provides",
    "requires_distributions",
}
_KNOWN_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS


@dataclass(frozen=True, slots=True)
class LocalPluginManifest:
    """在导入 Python 代码前解析完成的本地插件清单."""

    descriptor: PluginDescriptor
    entry: str
    requires_distributions: tuple[str, ...]
    origin: DirectoryPluginOrigin

    @property
    def plugin_id(self) -> str:
        return self.descriptor.plugin_id

    @classmethod
    def from_directory(cls, plugin_root: Path) -> "LocalPluginManifest":
        root = _resolve_directory(plugin_root, "插件目录")
        _reject_nested_symlinks(root)
        manifest_path = root / _MANIFEST_NAME
        if manifest_path.is_symlink():
            raise PluginDiscoveryError(
                "本地插件 manifest 不允许是符号链接: %s" % manifest_path
            )
        if not manifest_path.is_file():
            raise PluginDiscoveryError("本地插件缺少 %s: %s" % (_MANIFEST_NAME, root))

        try:
            manifest_bytes = manifest_path.read_bytes()
            raw = tomllib.loads(manifest_bytes.decode("utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise PluginDiscoveryError(
                "无法解析本地插件 manifest '%s'（%s）"
                % (manifest_path, type(exc).__name__)
            ) from exc
        if not isinstance(raw, dict):
            raise PluginDiscoveryError("本地插件 manifest 顶层必须是 TOML table")

        missing = sorted(_REQUIRED_FIELDS - set(raw))
        if missing:
            raise PluginDiscoveryError(
                "本地插件 manifest '%s' 缺少字段: %s"
                % (manifest_path, ", ".join(missing))
            )
        unknown = sorted(set(raw) - _KNOWN_FIELDS)
        if unknown:
            raise PluginDiscoveryError(
                "本地插件 manifest '%s' 包含未知字段: %s"
                % (manifest_path, ", ".join(unknown))
            )

        entry, entry_path = _parse_entry(root, raw["entry"], manifest_path)
        try:
            descriptor = PluginDescriptor(
                plugin_id=_require_string(raw, "plugin_id", manifest_path),
                version=_require_string(raw, "version", manifest_path),
                requires_core=_require_string(raw, "requires_core", manifest_path),
                requires_plugins=_require_string_tuple(
                    raw.get("requires_plugins", []),
                    "requires_plugins",
                    manifest_path,
                ),
                provides=_require_string_tuple(
                    raw.get("provides", []),
                    "provides",
                    manifest_path,
                ),
                schema_version=_require_integer(
                    raw,
                    "schema_version",
                    manifest_path,
                ),
            )
        except PluginCompatibilityError as exc:
            raise PluginDiscoveryError(
                "本地插件 manifest '%s' 的 descriptor 无效: %s" % (manifest_path, exc)
            ) from exc
        requirements = _parse_distribution_requirements(
            raw.get("requires_distributions", []),
            manifest_path,
        )
        fingerprint = _fingerprint(root, manifest_bytes)
        return cls(
            descriptor=descriptor,
            entry=entry,
            requires_distributions=requirements,
            origin=DirectoryPluginOrigin(
                plugin_root=root,
                manifest_path=manifest_path.resolve(strict=True),
                entry_path=entry_path,
                fingerprint=fingerprint,
            ),
        )


def _resolve_directory(path: Path, label: str) -> Path:
    if path.is_symlink():
        raise PluginDiscoveryError("%s不允许是符号链接: %s" % (label, path))
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise PluginDiscoveryError("%s不存在或无法访问: %s" % (label, path)) from exc
    if not resolved.is_dir():
        raise PluginDiscoveryError("%s必须是目录: %s" % (label, path))
    return resolved


def _reject_nested_symlinks(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PluginDiscoveryError("本地插件目录内不允许符号链接: %s" % path)


def _fingerprint(root: Path, manifest_bytes: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(b"plugin.toml\0")
    digest.update(manifest_bytes)
    python_files = sorted(
        (
            path
            for path in root.rglob("*.py")
            if "__pycache__" not in path.relative_to(root).parts
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    for path in python_files:
        relative = path.relative_to(root).as_posix()
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise PluginDiscoveryError(
                "无法读取本地插件代码 '%s'（%s）" % (path, type(exc).__name__)
            ) from exc
        digest.update(b"\0")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
    return digest.hexdigest()


def _parse_entry(
    root: Path,
    value: object,
    manifest_path: Path,
) -> tuple[str, Path]:
    if not isinstance(value, str):
        raise PluginDiscoveryError(
            "本地插件 manifest '%s' 的 entry 必须是字符串" % manifest_path
        )
    match = _ENTRY_PATTERN.fullmatch(value)
    if match is None:
        raise PluginDiscoveryError(
            "本地插件 entry 必须是根目录直接 Python 文件 'module.py': %s" % value
        )
    entry_path = root / value
    if entry_path.is_symlink():
        raise PluginDiscoveryError("本地插件 entry 不允许是符号链接: %s" % entry_path)
    try:
        resolved = entry_path.resolve(strict=True)
    except OSError as exc:
        raise PluginDiscoveryError("本地插件 entry 不存在: %s" % entry_path) from exc
    if resolved.parent != root or not resolved.is_file():
        raise PluginDiscoveryError("本地插件 entry 必须是插件根目录的直接 Python 文件")
    return value, resolved


def _require_string(
    raw: dict[str, Any],
    field: str,
    manifest_path: Path,
) -> str:
    value = raw[field]
    if not isinstance(value, str):
        raise PluginDiscoveryError(
            "本地插件 manifest '%s' 的 %s 必须是字符串" % (manifest_path, field)
        )
    return value


def _require_integer(
    raw: dict[str, Any],
    field: str,
    manifest_path: Path,
) -> int:
    value = raw[field]
    if not isinstance(value, int) or isinstance(value, bool):
        raise PluginDiscoveryError(
            "本地插件 manifest '%s' 的 %s 必须是整数" % (manifest_path, field)
        )
    return value


def _require_string_tuple(
    value: object,
    field: str,
    manifest_path: Path,
) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PluginDiscoveryError(
            "本地插件 manifest '%s' 的 %s 必须是字符串数组" % (manifest_path, field)
        )
    return tuple(value)


def _parse_distribution_requirements(
    value: object,
    manifest_path: Path,
) -> tuple[str, ...]:
    requirements = _require_string_tuple(
        value,
        "requires_distributions",
        manifest_path,
    )
    seen: set[str] = set()
    for requirement_text in requirements:
        try:
            requirement = Requirement(requirement_text)
        except InvalidRequirement as exc:
            raise PluginDiscoveryError(
                "本地插件 manifest '%s' 包含无效 Python distribution 要求: %s"
                % (manifest_path, requirement_text)
            ) from exc
        if requirement.url is not None or requirement.extras:
            raise PluginDiscoveryError(
                "本地插件 manifest '%s' 的 Python distribution 要求"
                "只支持名称和版本范围: %s" % (manifest_path, requirement_text)
            )
        normalized = requirement.name.lower().replace("_", "-")
        if normalized in seen:
            raise PluginDiscoveryError(
                "本地插件 manifest '%s' 包含重复 Python distribution 要求: %s"
                % (manifest_path, requirement.name)
            )
        seen.add(normalized)
    return requirements


__all__ = [
    "LocalPluginManifest",
]
