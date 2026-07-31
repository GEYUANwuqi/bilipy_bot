"""项目与插件的全副屏终端配置界面."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import click

from butterbot.app import ConfigError
from butterbot.plugin.discovery.catalog import PluginCandidate, PluginCatalog
from butterbot.plugin.discovery.settings import (
    LocalPluginSettings,
    PluginLifecyclePolicy,
    PluginSettings,
)

from .project import load_project_config, write_project_config
from .terminal import (
    dim,
    focused,
    full_screen,
    heading,
    is_interactive_terminal,
    pointer,
    prompt_mode,
    read_key,
    redraw,
    success,
    warning,
)

_RowKind = Literal["enabled", "path", "lifecycle", "plugin", "sources"]


@dataclass(frozen=True, slots=True)
class _MenuRow:
    kind: _RowKind
    label: str
    description: str
    plugin_name: str | None = None


def configure_plugins(path: str | Path = "config.yaml") -> int:
    """交互配置插件总开关、白名单、检索路径和生命周期."""
    config_path = Path(path).resolve()
    data = load_project_config(config_path)
    settings = PluginSettings.from_mapping(data)

    if is_interactive_terminal():
        result = _interactive_plugins(config_path, settings)
    else:
        result = _fallback_plugins(config_path, settings)
    if result is None:
        click.echo("已取消，配置未修改")
        return 0

    enabled, selected, plugin_path, lifecycle = result
    _write_plugin_settings(
        data,
        enabled=enabled,
        selected=selected,
        plugin_path=plugin_path,
        lifecycle=lifecycle,
    )
    written = write_project_config(data, config_path)
    click.echo(success("插件配置已写入: %s" % written))
    return 0


def configure_project(path: str | Path = "config.yaml") -> int:
    """交互配置项目级开关，并为 Source 自动发现保留入口."""
    config_path = Path(path).resolve()
    data = load_project_config(config_path)
    enabled = PluginSettings.from_mapping(data).enabled

    if is_interactive_terminal():
        result = _interactive_project(enabled, config_path)
    else:
        result = _fallback_project(enabled)
    if result is None:
        click.echo("已取消，配置未修改")
        return 0

    plugins = _mapping_section(data, "plugins")
    plugins["enabled"] = result
    data.setdefault("sources", {})
    written = write_project_config(data, config_path)
    click.echo(success("项目配置已写入: %s" % written))
    return 0


def _interactive_plugins(
    config_path: Path,
    settings: PluginSettings,
) -> tuple[bool, list[str], str, PluginLifecyclePolicy] | None:
    enabled = settings.enabled
    selected = list(settings.plugin_list)
    plugin_path = settings.plugin_path
    lifecycle = settings.lifecycle
    cursor = 0
    save = False

    with full_screen():
        try:
            while True:
                candidates = _index_candidates(config_path, plugin_path)
                rows = _plugin_rows(candidates, selected, plugin_path, lifecycle)
                cursor = min(cursor, len(rows) - 1)
                redraw(
                    _render_plugin_screen(
                        rows,
                        cursor=cursor,
                        enabled=enabled,
                        selected=selected,
                        config_path=config_path,
                    )
                )
                key = read_key()
                if key == "up":
                    cursor = (cursor - 1) % len(rows)
                elif key == "down":
                    cursor = (cursor + 1) % len(rows)
                elif key in ("q", "Q", "s", "S"):
                    save = True
                    break
                elif key == "esc":
                    break
                elif key in ("enter", "space"):
                    row = rows[cursor]
                    if row.kind == "enabled":
                        enabled = not enabled
                    elif row.kind == "plugin" and row.plugin_name is not None:
                        _toggle_selected(selected, row.plugin_name)
                    elif key == "enter" and row.kind == "path":
                        plugin_path = _configure_plugin_path(plugin_path)
                    elif key == "enter" and row.kind == "lifecycle":
                        lifecycle = _configure_lifecycle(lifecycle)
        except KeyboardInterrupt:
            save = False

    if not save:
        return None
    return enabled, selected, plugin_path, lifecycle


def _interactive_project(enabled: bool, config_path: Path) -> bool | None:
    cursor = 0
    save = False
    rows = (
        _MenuRow("enabled", "插件系统", "运行时唯一总开关"),
        _MenuRow("sources", "Sources", "自动发现与交互配置将在后续版本提供"),
    )

    with full_screen():
        try:
            while True:
                redraw(
                    _render_project_screen(
                        rows,
                        cursor=cursor,
                        enabled=enabled,
                        config_path=config_path,
                    )
                )
                key = read_key()
                if key == "up":
                    cursor = (cursor - 1) % len(rows)
                elif key == "down":
                    cursor = (cursor + 1) % len(rows)
                elif key in ("q", "Q", "s", "S"):
                    save = True
                    break
                elif key == "esc":
                    break
                elif key in ("enter", "space"):
                    row = rows[cursor]
                    if row.kind == "enabled":
                        enabled = not enabled
                    elif key == "enter" and row.kind == "sources":
                        _show_sources_placeholder()
        except KeyboardInterrupt:
            save = False

    return enabled if save else None


def _fallback_plugins(
    config_path: Path,
    settings: PluginSettings,
) -> tuple[bool, list[str], str, PluginLifecyclePolicy] | None:
    click.echo(heading("ButterBot 插件配置（兼容终端模式）"))
    enabled = click.confirm("启用插件系统", default=settings.enabled)
    plugin_path = click.prompt("插件检索目录", default=settings.plugin_path)
    LocalPluginSettings(path=plugin_path)
    candidates = _index_candidates(config_path, plugin_path)
    names = _choice_names(candidates, list(settings.plugin_list))
    descriptions = _candidate_descriptions(candidates, names)
    selected = _fallback_select_plugins(names, descriptions, settings.plugin_list)
    lifecycle = settings.lifecycle
    if click.confirm("修改生命周期超时", default=False):
        lifecycle = _configure_lifecycle(lifecycle)
    if not click.confirm("保存以上插件配置", default=True):
        return None
    return enabled, selected, plugin_path, lifecycle


def _fallback_project(enabled: bool) -> bool | None:
    click.echo(heading("ButterBot 配置（兼容终端模式）"))
    enabled = click.confirm("启用插件系统", default=enabled)
    click.echo(dim("Sources: 自动发现与交互配置将在后续版本提供"))
    if not click.confirm("保存以上项目配置", default=True):
        return None
    return enabled


def _fallback_select_plugins(
    names: tuple[str, ...],
    descriptions: tuple[str, ...],
    current: tuple[str, ...],
) -> list[str]:
    if not names:
        click.echo(warning("未发现插件"))
        return []

    click.echo(heading("可用插件:"))
    checked = {index for index, name in enumerate(names) if name in current}
    for index, (name, description) in enumerate(zip(names, descriptions), start=1):
        marker = "x" if index - 1 in checked else " "
        click.echo("  %s. [%s] %s  %s" % (index, marker, name, dim(description)))
    default = ",".join(str(index + 1) for index in sorted(checked))
    raw = click.prompt(
        "输入要启用的编号（逗号分隔，留空表示全不选）",
        default=default,
        show_default=bool(default),
    )
    selected_indices: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdecimal() and 1 <= int(part) <= len(names):
            selected_indices.add(int(part) - 1)
    return [name for index, name in enumerate(names) if index in selected_indices]


def _plugin_rows(
    candidates: tuple[PluginCandidate, ...],
    selected: list[str],
    plugin_path: str,
    lifecycle: PluginLifecyclePolicy,
) -> tuple[_MenuRow, ...]:
    rows = [
        _MenuRow("enabled", "插件系统总开关", "关闭不会清空插件选择"),
        _MenuRow("path", "检索目录", plugin_path),
        _MenuRow(
            "lifecycle",
            "生命周期",
            "start=%s  stop=%s  cleanup=%s  drain=%s"
            % (
                lifecycle.start_timeout,
                lifecycle.stop_timeout,
                lifecycle.cleanup_timeout,
                lifecycle.drain_timeout,
            ),
        ),
    ]
    for candidate in candidates:
        rows.append(
            _MenuRow(
                "plugin",
                candidate.plugin_name,
                "%s · %s" % (candidate.origin.kind, candidate.origin.location),
                candidate.plugin_name,
            )
        )
    discovered = {candidate.plugin_name for candidate in candidates}
    for plugin_name in selected:
        if plugin_name not in discovered:
            rows.append(
                _MenuRow(
                    "plugin",
                    plugin_name,
                    "missing · 未在当前来源中发现",
                    plugin_name,
                )
            )
    return tuple(rows)


def _render_plugin_screen(
    rows: tuple[_MenuRow, ...],
    *,
    cursor: int,
    enabled: bool,
    selected: list[str],
    config_path: Path,
) -> str:
    lines = [
        heading("── ButterBot 插件管理 ──"),
        dim("  ↑/↓ 或 j/k 移动  空格/Enter 切换  q 保存  Esc 取消"),
        dim("  在检索目录或生命周期上按 Enter 可进入编辑"),
        "",
        heading("系统"),
    ]
    for index, row in enumerate(rows):
        if index == 3:
            lines.extend(("", heading("插件")))
        prefix = "%s " % pointer() if index == cursor else "  "
        label = focused(row.label) if index == cursor else row.label
        if row.kind == "enabled":
            marker = success("[x]") if enabled else "[ ]"
        elif row.kind == "plugin":
            marker = success("[x]") if row.plugin_name in selected else "[ ]"
        else:
            marker = dim("[›]")
        lines.append("%s%s %s  %s" % (prefix, marker, label, dim(row.description)))
    if len(rows) == 3:
        lines.extend(("", warning("  未发现插件")))
    lines.extend(("", dim("配置文件: %s" % config_path)))
    return "\n".join(lines)


def _render_project_screen(
    rows: tuple[_MenuRow, ...],
    *,
    cursor: int,
    enabled: bool,
    config_path: Path,
) -> str:
    lines = [
        heading("── ButterBot 项目配置 ──"),
        dim("  ↑/↓ 或 j/k 移动  空格/Enter 切换  q 保存  Esc 取消"),
        "",
    ]
    for index, row in enumerate(rows):
        prefix = "%s " % pointer() if index == cursor else "  "
        label = focused(row.label) if index == cursor else row.label
        marker = success("[x]") if row.kind == "enabled" and enabled else "[ ]"
        if row.kind == "sources":
            marker = dim("[›]")
        lines.append("%s%s %s  %s" % (prefix, marker, label, dim(row.description)))
    lines.extend(("", dim("配置文件: %s" % config_path)))
    return "\n".join(lines)


def _configure_plugin_path(current: str) -> str:
    with prompt_mode():
        value = click.prompt("插件检索目录", default=current)
    LocalPluginSettings(path=value)
    return value


def _configure_lifecycle(
    current: PluginLifecyclePolicy,
) -> PluginLifecyclePolicy:
    values: dict[str, float] = {}
    with prompt_mode():
        click.echo(heading("插件生命周期超时（秒）"))
        for name, value in (
            ("start_timeout", current.start_timeout),
            ("stop_timeout", current.stop_timeout),
            ("cleanup_timeout", current.cleanup_timeout),
            ("drain_timeout", current.drain_timeout),
        ):
            values[name] = click.prompt(
                name,
                default=float(value),
                type=click.FloatRange(min=0.0, min_open=True),
            )
    return PluginLifecyclePolicy(**values)


def _show_sources_placeholder() -> None:
    with prompt_mode():
        click.echo(heading("Sources"))
        click.echo("自动发现与交互配置将在后续版本提供。")
        click.echo("现有 YAML 内容不会被修改。")
        click.pause("按任意键返回...")


def _index_candidates(
    config_path: Path,
    plugin_path: str,
) -> tuple[PluginCandidate, ...]:
    return PluginCatalog.index_candidates(
        local=LocalPluginSettings(path=plugin_path),
        config_root=config_path.parent,
    )


def _choice_names(
    candidates: tuple[PluginCandidate, ...],
    selected: list[str],
) -> tuple[str, ...]:
    discovered = tuple(candidate.plugin_name for candidate in candidates)
    return discovered + tuple(name for name in selected if name not in discovered)


def _candidate_descriptions(
    candidates: tuple[PluginCandidate, ...],
    names: tuple[str, ...],
) -> tuple[str, ...]:
    by_name = {
        candidate.plugin_name: "%s · %s"
        % (candidate.origin.kind, candidate.origin.location)
        for candidate in candidates
    }
    return tuple(by_name.get(name, "missing · 未发现") for name in names)


def _toggle_selected(selected: list[str], plugin_name: str) -> None:
    if plugin_name in selected:
        selected.remove(plugin_name)
    else:
        selected.append(plugin_name)


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
