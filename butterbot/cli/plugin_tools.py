"""插件候选查看与模拟导入操作."""

from __future__ import annotations

from pathlib import Path

import click

from butterbot import __version__
from butterbot.plugin import PluginError
from butterbot.plugin._internal import PluginBootstrap
from butterbot.plugin.discovery.directory import validate_distribution_requirements


def list_plugins(config_path: Path) -> int:
    """静态列出配置可发现的全部插件候选."""
    bootstrap = PluginBootstrap(config_path.resolve())
    settings = bootstrap.settings
    candidates = bootstrap.inspect_candidates()
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
    """只导入 YAML 选中的插件，并报告配置拦截结果."""
    bootstrap = PluginBootstrap(config_path.resolve())
    settings = bootstrap.settings
    candidates = bootstrap.inspect_candidates()
    selected = set(settings.plugin_list)
    failed = False

    click.echo("NAME\tRESULT\tLOCATION")
    discovered_names = {candidate.plugin_name for candidate in candidates}
    for candidate in candidates:
        if not settings.enabled:
            result = "BLOCKED: plugins.enabled=false"
        elif candidate.plugin_name not in selected:
            result = "BLOCKED: not in plugin_list"
        else:
            try:
                validate_distribution_requirements(
                    candidate.plugin_id or candidate.plugin_name,
                    candidate.requires_distributions,
                )
                loaded = candidate.load()
                implementation_name = type(loaded.instance).__name__
                if implementation_name != candidate.plugin_name:
                    raise PluginError(
                        "插件名称 '%s' 与实现类名 '%s' 不一致"
                        % (candidate.plugin_name, implementation_name)
                    )
                if (
                    candidate.plugin_id is not None
                    and loaded.descriptor.plugin_id != candidate.plugin_id
                ):
                    raise PluginError(
                        "候选 '%s' 返回的 plugin_id 是 '%s'"
                        % (candidate.plugin_id, loaded.descriptor.plugin_id)
                    )
                if not loaded.descriptor.supports_core(__version__):
                    raise PluginError(
                        "插件 '%s' 要求 ButterBot %s，当前为 %s"
                        % (
                            loaded.descriptor.plugin_id,
                            loaded.descriptor.requires_core,
                            __version__,
                        )
                    )
            except PluginError as exc:
                result = "FAILED: %s" % exc
                failed = True
            else:
                result = "LOADED"
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
        if settings.enabled:
            failed = True
        click.echo("%s\t%s\t<not found>" % (missing, result))

    if failed:
        click.echo("插件模拟导入发现错误", err=True)
        return 1
    click.echo("插件模拟导入完成")
    return 0


__all__ = ["check_plugins", "list_plugins"]
