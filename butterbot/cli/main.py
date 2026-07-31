"""ButterBot Click 命令树与统一错误出口."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import click
import yaml

from butterbot import __version__
from butterbot.app import ConfigError
from butterbot.plugin import PluginError

from .configurator import configure_plugins, configure_project
from .errors import CliError
from .plugin_tools import check_plugins, list_plugins
from .project import initialize_project
from .runtime import (
    close_application,
    pause_application,
    restart_application,
    run_application,
    show_status,
)

_CONFIG_PATH_TYPE = click.Path(
    path_type=Path,
    dir_okay=False,
    resolve_path=False,
)


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(version=__version__, prog_name="ButterBot")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """运行和管理 ButterBot 应用."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command("run")
@click.argument("application", required=False)
@click.option("-path", "--path", "application_override", help="覆盖应用入口路径")
@click.option(
    "-config",
    "--config",
    "config_path",
    default=Path("config.yaml"),
    show_default="当前目录的 config.yaml",
    type=_CONFIG_PATH_TYPE,
    help="YAML 配置文件",
)
@click.option("--background", is_flag=True, help="在后台启动并立即返回")
@click.option("--debug", is_flag=True, help="保留完整异常信息")
def run_command(
    application: str | None,
    application_override: str | None,
    config_path: Path,
    background: bool,
    debug: bool,
) -> int:
    """运行应用；APPLICATION 默认是 app.app."""
    return run_application(
        application=application,
        application_override=application_override,
        config_path=config_path,
        background=background,
        debug=debug,
    )


@cli.command("init")
def init_command() -> int:
    """在当前目录创建完整可运行项目."""
    created = initialize_project(Path.cwd())
    click.echo("ButterBot 项目已初始化:")
    for path in created:
        click.echo("  %s" % path.relative_to(Path.cwd()))
    click.echo("运行命令: butterbot run")
    return 0


@cli.command("config")
@click.option(
    "-config",
    "--config",
    "config_path",
    default=Path("config.yaml"),
    show_default="当前目录的 config.yaml",
    type=_CONFIG_PATH_TYPE,
    help="YAML 配置文件",
)
def config_command(config_path: Path) -> int:
    """全屏交互配置当前项目."""
    return configure_project(config_path)


@cli.group("plugin", invoke_without_command=True)
@click.option(
    "-config",
    "--config",
    "config_path",
    default=Path("config.yaml"),
    show_default="当前目录的 config.yaml",
    type=_CONFIG_PATH_TYPE,
    help="YAML 配置文件",
)
@click.pass_context
def plugin_command(ctx: click.Context, config_path: Path) -> int | None:
    """全屏配置、查看或检查插件."""
    if ctx.invoked_subcommand is None:
        return configure_plugins(config_path)
    return None


def _plugin_config_option(function):
    return click.option(
        "-config",
        "--config",
        "config_path",
        default=None,
        type=_CONFIG_PATH_TYPE,
        help="覆盖父命令的 YAML 配置文件",
    )(function)


def _effective_plugin_config(ctx: click.Context, config_path: Path | None) -> Path:
    if config_path is not None:
        return config_path
    assert ctx.parent is not None
    parent_path = ctx.parent.params["config_path"]
    assert isinstance(parent_path, Path)
    return parent_path


@plugin_command.command("list")
@_plugin_config_option
@click.pass_context
def plugin_list_command(ctx: click.Context, config_path: Path | None) -> int:
    """静态列出发现的全部插件及其来源."""
    return list_plugins(_effective_plugin_config(ctx, config_path))


@plugin_command.command("check")
@_plugin_config_option
@click.pass_context
def plugin_check_command(ctx: click.Context, config_path: Path | None) -> int:
    """模拟导入，并报告加载或配置拦截结果."""
    return check_plugins(_effective_plugin_config(ctx, config_path))


@cli.command("restart")
def restart_command() -> int:
    """使用上次入口和配置完整重启应用."""
    return restart_application()


@cli.command("stop")
def stop_command() -> int:
    """暂停应用进程."""
    return pause_application()


@cli.command("close")
def close_command() -> int:
    """优雅关闭应用进程."""
    return close_application()


@cli.command("status")
def status_command() -> int:
    """显示应用运行状态."""
    return show_status()


def main(argv: Sequence[str] | None = None) -> int:
    """执行 Click 命令树，并把领域异常转换为稳定退出码."""
    arguments = list(argv) if argv is not None else sys.argv[1:]
    debug = "--debug" in arguments
    try:
        result = cli.main(
            args=arguments,
            prog_name="butterbot",
            standalone_mode=False,
        )
    except click.ClickException as exc:
        exc.show(file=sys.stderr)
        return exc.exit_code
    except click.Abort:
        click.echo("已取消。", err=True)
        return 1
    except CliError as exc:
        if debug:
            raise
        click.echo("错误: %s" % exc, err=True)
        return exc.exit_code
    except (ConfigError, PluginError, FileNotFoundError, yaml.YAMLError) as exc:
        if debug:
            raise
        click.echo("配置无效: %s" % exc, err=True)
        return 1
    return int(result or 0)


__all__ = ["cli", "main"]
