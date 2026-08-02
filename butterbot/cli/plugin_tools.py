"""显式插件管理命令使用的只读工具."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import click

from butterbot.app.config import _load_resolved_yaml
from butterbot.core.exceptions import ConfigError
from butterbot.plugin.discovery.catalog import PluginCatalog
from butterbot.plugin.discovery.settings import PluginSettings


def list_plugins(config_path: Path) -> int:
    """静态列出候选元数据，不导入候选插件代码."""
    resolved = config_path.resolve()
    settings = _settings(resolved)
    candidates = PluginCatalog.index_candidates(
        local=settings.local,
        config_root=resolved.parent,
    )
    selected = set(settings.plugin_list)

    click.echo("ID\tNAME\tVERSION\tORIGIN\tCONFIGURED\tSYSTEM\tLOCATION")
    for candidate in candidates:
        descriptor = candidate.descriptor
        version = descriptor.version if descriptor is not None else "<load required>"
        plugin_id = (
            descriptor.plugin_id
            if descriptor is not None
            else candidate.plugin_id or "<load required>"
        )
        click.echo(
            "%s\t%s\t%s\t%s\t%s\t%s\t%s"
            % (
                plugin_id,
                candidate.plugin_name,
                version,
                candidate.origin.kind,
                "yes" if candidate.plugin_name in selected else "no",
                "enabled" if settings.enabled else "disabled",
                candidate.origin.location,
            )
        )
    return 0


def check_plugins(config_path: Path) -> int:
    """在短生命周期子进程中导入并校验选中的候选插件."""
    resolved = config_path.resolve()
    settings = _settings(resolved)
    candidates = PluginCatalog.index_candidates(
        local=settings.local,
        config_root=resolved.parent,
    )
    selected = set(settings.plugin_list)
    discovered_names = {candidate.plugin_name for candidate in candidates}
    results: dict[str, str] = {}

    if settings.enabled and selected:
        results = _run_check_worker(resolved)

    failed = False
    click.echo("NAME\tRESULT\tLOCATION")
    for candidate in candidates:
        if not settings.enabled:
            result = "BLOCKED: plugins.enabled=false"
        elif candidate.plugin_name not in selected:
            result = "BLOCKED: not in plugin_list"
        else:
            result = results.get(candidate.plugin_name, "FAILED: WorkerProtocolError")
            failed = failed or result.startswith("FAILED")
        click.echo(
            "%s\t%s\t%s:%s"
            % (
                candidate.plugin_name,
                result,
                candidate.origin.kind,
                candidate.origin.location,
            )
        )

    for missing in sorted(selected - discovered_names):
        result = "BLOCKED: plugins.enabled=false" if not settings.enabled else "MISSING"
        failed = failed or settings.enabled
        click.echo("%s\t%s\t<not found>" % (missing, result))

    if failed:
        click.echo("插件隔离校验发现错误", err=True)
        return 1
    click.echo("插件隔离校验完成")
    return 0


def _settings(config_path: Path) -> PluginSettings:
    data = _load_resolved_yaml(config_path)
    return PluginSettings.from_mapping(data)


def _run_check_worker(config_path: Path) -> dict[str, str]:
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "butterbot.cli._plugin_check_worker",
                str(config_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise ConfigError("插件隔离校验超过 60 秒") from exc
    if result.returncode != 0:
        raise ConfigError("插件隔离校验子进程失败（退出码 %s）" % result.returncode)
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ConfigError("插件隔离校验子进程返回了无效结果") from exc
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in payload.items()
    ):
        raise ConfigError("插件隔离校验子进程返回了无效结果")
    return payload


__all__ = ["check_plugins", "list_plugins"]
