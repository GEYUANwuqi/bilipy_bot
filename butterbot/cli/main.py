"""ButterBot 命令行入口."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

import yaml

from butterbot import __version__
from butterbot.app import ConfigError
from butterbot.plugin import PluginBootstrap, PluginError
from butterbot.plugin.discovery.directory import validate_distribution_requirements

from .configurator import configure_plugins, configure_project
from .errors import CliError
from .loader import load_application
from .project import initialize_project
from .state import RuntimeState, StateStore, is_process_alive

_STATE_DIRECTORY = ".butterbot"
_STATE_FILENAME = "runtime.json"
_LOG_FILENAME = "butterbot.log"
_STOP_TIMEOUT = 10.0
_BACKGROUND_START_TIMEOUT = 5.0
_STATUS_NOT_RUNNING = 3
_DEFAULT_APPLICATION_PATH = "app.app"
_DEFAULT_CONFIG_PATH = "config.yaml"


def main(argv: Sequence[str] | None = None) -> int:
    """解析并执行 CLI 命令."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except CliError as exc:
        if getattr(args, "debug", False):
            raise
        print("错误: %s" % exc, file=sys.stderr)
        return exc.exit_code
    except (ConfigError, PluginError, FileNotFoundError, yaml.YAMLError) as exc:
        if getattr(args, "debug", False):
            raise
        print("配置无效: %s" % exc, file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="butterbot",
        description="运行和管理 ButterBot 应用",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="运行应用")
    run_parser.add_argument(
        "application",
        nargs="?",
        help="应用入口，默认 app.app",
    )
    run_parser.add_argument(
        "-path",
        "--path",
        dest="application_override",
        help="覆盖应用入口路径",
    )
    _add_config_argument(run_parser)
    run_parser.add_argument(
        "--background",
        action="store_true",
        help="在后台启动并立即返回",
    )
    run_parser.add_argument(
        "--debug",
        action="store_true",
        help="保留完整异常信息",
    )
    run_parser.set_defaults(handler=_run)

    init_parser = commands.add_parser("init", help="创建完整可运行项目")
    init_parser.set_defaults(handler=_init_project)

    config_parser = commands.add_parser("config", help="交互配置当前项目")
    _add_config_argument(config_parser)
    config_parser.set_defaults(handler=_configure_project)

    restart_parser = commands.add_parser("restart", help="完整重启应用")
    restart_parser.set_defaults(handler=_restart)

    stop_parser = commands.add_parser("stop", help="暂停应用")
    stop_parser.set_defaults(handler=_stop)

    close_parser = commands.add_parser("close", help="优雅关闭应用")
    close_parser.set_defaults(handler=_close)

    status_parser = commands.add_parser("status", help="显示应用运行状态")
    status_parser.set_defaults(handler=_status)

    plugins_parser = commands.add_parser("plugin", help="配置和检查插件")
    _add_config_argument(plugins_parser)
    plugins_parser.set_defaults(handler=_configure_plugins)
    plugin_commands = plugins_parser.add_subparsers(
        dest="plugin_command",
    )
    plugins_list_parser = plugin_commands.add_parser("list", help="列出已发现插件")
    _add_config_argument(plugins_list_parser, suppress_default=True)
    plugins_list_parser.set_defaults(handler=_plugins_list)

    plugins_check_parser = plugin_commands.add_parser(
        "check",
        help="模拟导入并报告加载或配置拦截结果",
    )
    _add_config_argument(plugins_check_parser, suppress_default=True)
    plugins_check_parser.set_defaults(handler=_plugins_check)
    return parser


def _init_project(args: argparse.Namespace) -> int:
    del args
    created = initialize_project(Path.cwd())
    print("ButterBot 项目已初始化:")
    for path in created:
        print("  %s" % path.relative_to(Path.cwd()))
    print("运行命令: butterbot run")
    return 0


def _configure_project(args: argparse.Namespace) -> int:
    return configure_project(args.config_path)


def _configure_plugins(args: argparse.Namespace) -> int:
    return configure_plugins(args.config_path)


def _plugins_list(args: argparse.Namespace) -> int:
    bootstrap = PluginBootstrap(_resolve_config_path(args.config_path))
    settings = bootstrap.settings
    candidates = bootstrap.inspect_candidates()
    selected = set(settings.plugin_list)

    print("ID\tNAME\tVERSION\tORIGIN\tCONFIGURED\tSYSTEM\tLOCATION")
    for candidate in candidates:
        descriptor = candidate.descriptor
        version = descriptor.version if descriptor is not None else "<load required>"
        plugin_id = (
            descriptor.plugin_id
            if descriptor is not None
            else candidate.plugin_id or "<load required>"
        )
        print(
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


def _plugins_check(args: argparse.Namespace) -> int:
    bootstrap = PluginBootstrap(_resolve_config_path(args.config_path))
    settings = bootstrap.settings
    candidates = bootstrap.inspect_candidates()
    selected = set(settings.plugin_list)
    failed = False

    print("NAME\tRESULT\tLOCATION")
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
        print(
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
        print("%s\t%s\t<not found>" % (missing, result))

    if failed:
        print("插件模拟导入发现错误", file=sys.stderr)
        return 1
    print("插件模拟导入完成")
    return 0


def _run(args: argparse.Namespace) -> int:
    working_directory = Path.cwd()
    application_path = _application_path(args)
    config_path = _resolve_config_path(args.config_path)
    store = _state_store(working_directory)
    existing = store.refresh()
    if existing is not None and existing.status == "paused":
        return _resume_paused_process(store, existing)
    if args.background:
        pid = _spawn_background(
            application_path=application_path,
            config_path=config_path,
            debug=args.debug,
            working_directory=working_directory,
        )
        print("ButterBot 已在后台启动（PID %s）" % pid)
        return 0

    application = load_application(application_path)
    bootstrap = PluginBootstrap(config_path)
    app = bootstrap.build(application)
    state = RuntimeState.running(
        pid=os.getpid(),
        debug=args.debug,
        working_directory=str(working_directory),
        application_path=application_path,
        config_path=str(config_path),
        log_file=str(_log_file(working_directory)),
    )
    store.claim(state)

    exit_code = 1
    try:
        app.run()
        exit_code = 0
        return 0
    finally:
        store.mark_stopped(state.token, exit_code)


def _status(args: argparse.Namespace) -> int:
    del args
    state = _state_store(Path.cwd()).refresh()
    if state is None:
        print("ButterBot 未登记")
        return _STATUS_NOT_RUNNING
    if state.status == "paused" and is_process_alive(state):
        print("ButterBot 已暂停（PID %s）" % state.pid)
        return 0
    if is_process_alive(state):
        print("ButterBot 正在运行（PID %s）" % state.pid)
        return 0
    print("ButterBot 已停止")
    return _STATUS_NOT_RUNNING


def _stop(args: argparse.Namespace) -> int:
    del args
    store = _state_store(Path.cwd())
    state = store.refresh()
    if state is None:
        raise CliError("没有找到运行状态: %s" % store.path)
    if state.status == "paused" and is_process_alive(state):
        print("ButterBot 已处于暂停状态（PID %s）" % state.pid)
        return 0
    if not is_process_alive(state) or state.pid is None:
        raise CliError("ButterBot 当前未运行", exit_code=_STATUS_NOT_RUNNING)

    stop_signal = getattr(signal, "SIGSTOP", None)
    if stop_signal is None:
        raise CliError("当前平台不支持暂停进程")
    store.mark_paused(state.token)
    try:
        os.kill(state.pid, stop_signal)
    except ProcessLookupError:
        store.mark_running(state.token)
        store.refresh()
        raise CliError("ButterBot 当前未运行", exit_code=_STATUS_NOT_RUNNING) from None
    except PermissionError as exc:
        store.mark_running(state.token)
        raise CliError("没有权限暂停 ButterBot 进程（PID %s）" % state.pid) from exc

    print("ButterBot 已暂停（PID %s）" % state.pid)
    return 0


def _close(args: argparse.Namespace) -> int:
    del args
    state = _stop_managed_process(_state_store(Path.cwd()))
    print("ButterBot 已关闭（配置 %s）" % state.config_path)
    return 0


def _restart(args: argparse.Namespace) -> int:
    del args
    store = _state_store(Path.cwd())
    state = store.refresh()
    if state is None:
        raise CliError("没有可重启的应用记录")
    if is_process_alive(state):
        _stop_managed_process(store)

    # 必须等旧 PID 完全消失后才创建新解释器；不复用模块、BotApp 或 RuntimeConfig。
    pid = _spawn_background(
        application_path=state.application_path,
        config_path=Path(state.config_path),
        debug=state.debug,
        working_directory=Path(state.working_directory),
    )
    print("ButterBot 已完整重启（PID %s）" % pid)
    return 0


def _stop_managed_process(store: StateStore) -> RuntimeState:
    state = store.refresh()
    if state is None:
        raise CliError("没有找到运行状态: %s" % store.path)
    if not is_process_alive(state) or state.pid is None:
        raise CliError("ButterBot 当前未运行", exit_code=_STATUS_NOT_RUNNING)

    if state.status == "paused":
        _resume_process(store, state)
    try:
        os.kill(state.pid, signal.SIGTERM)
    except ProcessLookupError:
        store.mark_stopped(state.token, state.exit_code)
        raise CliError("ButterBot 当前未运行", exit_code=_STATUS_NOT_RUNNING) from None
    except PermissionError as exc:
        raise CliError("没有权限关闭 ButterBot 进程（PID %s）" % state.pid) from exc

    deadline = time.monotonic() + _STOP_TIMEOUT
    while time.monotonic() < deadline:
        if not is_process_alive(state):
            store.mark_stopped(state.token, 0)
            return state
        time.sleep(0.05)
    raise CliError("等待 ButterBot 优雅关闭超时（PID %s）；未执行强制终止" % state.pid)


def _spawn_background(
    *,
    application_path: str,
    config_path: Path,
    debug: bool,
    working_directory: Path,
) -> int:
    store = _state_store(working_directory)
    existing = store.refresh()
    if existing is not None and is_process_alive(existing):
        raise CliError("已有 ButterBot 实例正在运行（PID %s）" % existing.pid)

    command = [
        sys.executable,
        "-m",
        "butterbot.cli",
        "run",
        "-path",
        application_path,
        "-config",
        str(config_path),
    ]
    if debug:
        command.append("--debug")

    log_file = _log_file(working_directory)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["PYTHONUNBUFFERED"] = "1"
    try:
        with log_file.open("ab") as output:
            process = subprocess.Popen(
                command,
                cwd=working_directory,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except OSError as exc:
        raise CliError("无法启动 ButterBot 后台进程") from exc

    deadline = time.monotonic() + _BACKGROUND_START_TIMEOUT
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise CliError(
                "ButterBot 后台启动失败（退出码 %s），请检查日志 %s"
                % (return_code, log_file)
            )
        state = store.load()
        if state is not None and state.pid == process.pid and is_process_alive(state):
            return process.pid
        time.sleep(0.05)

    try:
        process.terminate()
    except ProcessLookupError:
        pass
    raise CliError("等待 ButterBot 后台进程登记状态超时")


def _state_store(working_directory: Path) -> StateStore:
    return StateStore(working_directory / _STATE_DIRECTORY / _STATE_FILENAME)


def _log_file(working_directory: Path) -> Path:
    return (working_directory / _STATE_DIRECTORY / _LOG_FILENAME).resolve()


def _add_config_argument(
    parser: argparse.ArgumentParser,
    *,
    suppress_default: bool = False,
) -> None:
    default = argparse.SUPPRESS if suppress_default else _DEFAULT_CONFIG_PATH
    parser.add_argument(
        "-config",
        "--config",
        dest="config_path",
        default=default,
        help="YAML 配置文件，默认当前目录的 config.yaml",
    )


def _application_path(args: argparse.Namespace) -> str:
    return args.application_override or args.application or _DEFAULT_APPLICATION_PATH


def _resolve_config_path(value: str) -> Path:
    return Path(value).resolve()


def _resume_paused_process(store: StateStore, state: RuntimeState) -> int:
    if state.pid is None or not is_process_alive(state):
        store.mark_stopped(state.token, state.exit_code)
        raise CliError("暂停的 ButterBot 进程已经退出")
    _resume_process(store, state)
    print(
        "检测到暂停的实例，已恢复原进程（PID %s）；"
        "未创建新实例，如需新实例请使用 restart，或先 close 再 run" % state.pid
    )
    return 0


def _continue_process(pid: int) -> None:
    continue_signal = getattr(signal, "SIGCONT", None)
    if continue_signal is None:
        raise CliError("当前平台不支持恢复暂停进程")
    try:
        os.kill(pid, continue_signal)
    except ProcessLookupError:
        raise CliError("暂停的 ButterBot 进程已经退出") from None
    except PermissionError as exc:
        raise CliError("没有权限恢复 ButterBot 进程（PID %s）" % pid) from exc


def _resume_process(store: StateStore, state: RuntimeState) -> None:
    if state.pid is None:
        raise CliError("暂停的 ButterBot 进程已经退出")
    store.mark_running(state.token)
    try:
        _continue_process(state.pid)
    except BaseException:
        store.mark_paused(state.token)
        raise
