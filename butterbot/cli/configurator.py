"""项目与插件的行式可视化终端配置界面."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from butterbot.app import ConfigError
from butterbot.plugin.discovery.catalog import PluginCandidate, PluginCatalog
from butterbot.plugin.discovery.settings import (
    LocalPluginSettings,
    PluginLifecyclePolicy,
    PluginSettings,
)

from .project import load_project_config, write_project_config


def configure_plugins(path: str | Path = "config.yaml") -> int:
    """交互配置插件总开关、白名单、检索路径和生命周期."""
    config_path = Path(path).resolve()
    data = load_project_config(config_path)
    settings = PluginSettings.from_mapping(data)
    enabled = settings.enabled
    selected = list(settings.plugin_list)
    plugin_path = settings.plugin_path
    lifecycle = settings.lifecycle

    while True:
        candidates = _index_candidates(config_path, plugin_path)
        choice_names = _choice_names(candidates, selected)
        _render_plugin_screen(
            candidates,
            enabled=enabled,
            selected=selected,
            plugin_path=plugin_path,
            lifecycle=lifecycle,
        )
        choice = input("选择插件编号或操作，然后按 Enter: ").strip()
        lowered = choice.lower()
        if lowered == "e":
            enabled = not enabled
            continue
        if lowered == "p":
            value = input("插件检索目录（留空保持不变）: ").strip()
            if value:
                LocalPluginSettings(path=value)
                plugin_path = value
            continue
        if lowered == "l":
            lifecycle = _configure_lifecycle(lifecycle)
            continue
        if lowered in ("s", ""):
            _write_plugin_settings(
                data,
                enabled=enabled,
                selected=selected,
                plugin_path=plugin_path,
                lifecycle=lifecycle,
            )
            written = write_project_config(data, config_path)
            print("插件配置已写入: %s" % written)
            return 0
        if lowered == "q":
            print("已取消，配置未修改")
            return 0
        if choice.isdecimal() and 1 <= int(choice) <= len(choice_names):
            plugin_name = choice_names[int(choice) - 1]
            if plugin_name in selected:
                selected.remove(plugin_name)
            else:
                selected.append(plugin_name)
            continue
        print("无效选择: %s" % choice)


def configure_project(path: str | Path = "config.yaml") -> int:
    """交互配置项目级开关，并为 Source 自动发现保留入口."""
    config_path = Path(path).resolve()
    data = load_project_config(config_path)
    enabled = PluginSettings.from_mapping(data).enabled

    while True:
        print("\nButterBot 配置")
        print("=" * 60)
        print("[E] 插件系统: %s" % ("已启用" if enabled else "已关闭"))
        print("[1] Sources: 自动发现与交互配置将在后续版本提供")
        print("[S/Enter] 保存    [Q] 取消")
        choice = input("选择操作，然后按 Enter: ").strip().lower()
        if choice == "e":
            enabled = not enabled
            continue
        if choice == "1":
            print("Sources 配置暂为占位；现有 YAML 内容不会被修改。")
            continue
        if choice in ("s", ""):
            plugins = _mapping_section(data, "plugins")
            plugins["enabled"] = enabled
            data.setdefault("sources", {})
            written = write_project_config(data, config_path)
            print("项目配置已写入: %s" % written)
            return 0
        if choice == "q":
            print("已取消，配置未修改")
            return 0
        print("无效选择: %s" % choice)


def _index_candidates(
    config_path: Path,
    plugin_path: str,
) -> tuple[PluginCandidate, ...]:
    return PluginCatalog.index_candidates(
        local=LocalPluginSettings(path=plugin_path),
        config_root=config_path.parent,
    )


def _render_plugin_screen(
    candidates: tuple[PluginCandidate, ...],
    *,
    enabled: bool,
    selected: list[str],
    plugin_path: str,
    lifecycle: PluginLifecyclePolicy,
) -> None:
    print("\nButterBot 插件配置")
    print("=" * 80)
    print("[E] 插件系统总开关: %s" % ("已启用" if enabled else "已关闭"))
    print("[P] 检索目录: %s" % plugin_path)
    print(
        "[L] 生命周期: start=%s stop=%s cleanup=%s drain=%s"
        % (
            lifecycle.start_timeout,
            lifecycle.stop_timeout,
            lifecycle.cleanup_timeout,
            lifecycle.drain_timeout,
        )
    )
    print("-" * 80)
    if not candidates:
        print("未发现插件")
    for index, candidate in enumerate(candidates, start=1):
        mark = "x" if candidate.plugin_name in selected else " "
        print(
            "%2d. [%s] %-28s %s:%s"
            % (
                index,
                mark,
                candidate.plugin_name,
                candidate.origin.kind,
                candidate.origin.location,
            )
        )
    candidate_names = {candidate.plugin_name for candidate in candidates}
    missing = [name for name in selected if name not in candidate_names]
    for index, name in enumerate(missing, start=len(candidates) + 1):
        print("%2d. [x] %-28s missing:<未发现>" % (index, name))
    print("-" * 80)
    print("输入编号切换插件；[S/Enter] 保存；[Q] 取消")


def _configure_lifecycle(
    current: PluginLifecyclePolicy,
) -> PluginLifecyclePolicy:
    values: dict[str, float] = {}
    for name, value in (
        ("start_timeout", current.start_timeout),
        ("stop_timeout", current.stop_timeout),
        ("cleanup_timeout", current.cleanup_timeout),
        ("drain_timeout", current.drain_timeout),
    ):
        raw = input("%s 秒 [%s]: " % (name, value)).strip()
        try:
            values[name] = value if not raw else float(raw)
        except ValueError as exc:
            raise ConfigError("生命周期超时必须是数字: %s" % raw) from exc
    return PluginLifecyclePolicy(**values)


def _choice_names(
    candidates: tuple[PluginCandidate, ...],
    selected: list[str],
) -> tuple[str, ...]:
    discovered = tuple(candidate.plugin_name for candidate in candidates)
    return discovered + tuple(name for name in selected if name not in discovered)


def _write_plugin_settings(
    data: dict[str, Any],
    *,
    enabled: bool,
    selected: list[str],
    plugin_path: str,
    lifecycle: PluginLifecyclePolicy,
) -> None:
    plugins = _mapping_section(data, "plugins")
    plugins["enabled"] = enabled
    plugins["plugin_list"] = list(selected)
    plugins["plugin_path"] = plugin_path
    plugins["lifecycle"] = {
        "start_timeout": lifecycle.start_timeout,
        "stop_timeout": lifecycle.stop_timeout,
        "cleanup_timeout": lifecycle.cleanup_timeout,
        "drain_timeout": lifecycle.drain_timeout,
    }


def _mapping_section(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if value is None:
        section: dict[str, Any] = {}
        data[key] = section
        return section
    if not isinstance(value, Mapping):
        raise ConfigError("配置项 '%s' 应为映射" % key)
    section = dict(value)
    data[key] = section
    return section


__all__ = ["configure_plugins", "configure_project"]
