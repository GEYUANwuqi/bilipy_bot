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
from butterbot.plugin import (
    PluginBootstrap,
    PluginDescriptor,
    PluginError,
)

from .errors import CliError
from .loader import load_app, load_app_factory, resolve_entrypoint
from .state import RuntimeState, StateStore, is_process_alive

_STATE_DIRECTORY = ".butterbot"
_STATE_FILENAME = "runtime.json"
_LOG_FILENAME = "butterbot.log"
_STOP_TIMEOUT = 10.0
_BACKGROUND_START_TIMEOUT = 5.0
_STATUS_NOT_RUNNING = 3


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
    run_parser.add_argument("entrypoint", help="BotApp 对象，格式为 module:attribute")
    run_parser.add_argument(
        "--background",
        action="store_true",
        help="在后台启动并立即返回",
    )
    run_parser.add_argument(
        "--debug",
        action="store_true",
        help="保留完整异常信息，供调试和后续 BotApp 参数使用",
    )
    run_parser.set_defaults(handler=_run)

    check_parser = commands.add_parser("check", help="检查当前目录的 config.yaml")
    check_parser.add_argument(
        "entrypoint",
        nargs="?",
        help="插件模式应用 factory，格式为 module:attribute",
    )
    check_parser.set_defaults(handler=_check_config)

    restart_parser = commands.add_parser("restart", help="完整重启应用")
    restart_parser.set_defaults(handler=_restart)

    stop_parser = commands.add_parser("stop", help="暂停应用")
    stop_parser.set_defaults(handler=_stop)

    close_parser = commands.add_parser("close", help="优雅关闭应用")
    close_parser.set_defaults(handler=_close)

    status_parser = commands.add_parser("status", help="显示应用运行状态")
    status_parser.set_defaults(handler=_status)

    plugins_parser = commands.add_parser("plugins", help="管理启动期插件")
    plugin_commands = plugins_parser.add_subparsers(
        dest="plugin_command",
        required=True,
    )
    plugins_list_parser = plugin_commands.add_parser("list", help="列出已发现插件")
    plugins_list_parser.set_defaults(handler=_plugins_list)

    plugins_check_parser = plugin_commands.add_parser(
        "check",
        help="检查插件发现、导入和注册",
    )
    plugins_check_parser.add_argument(
        "entrypoint",
        nargs="?",
        help="插件模式应用 factory，格式为 module:attribute",
    )
    plugins_check_parser.set_defaults(handler=_check_config)

    plugins_init_parser = plugin_commands.add_parser(
        "init",
        help="创建最小本地目录插件",
    )
    plugins_init_parser.add_argument("plugin_id", help="全局稳定插件 ID")
    plugins_init_parser.add_argument(
        "--path",
        default="./plugins",
        help="本地插件根目录，默认 ./plugins",
    )
    plugins_init_parser.set_defaults(handler=_plugins_init)
    return parser


def _check_config(args: argparse.Namespace) -> int:
    path = Path("config.yaml").resolve()
    bootstrap = PluginBootstrap(path)
    if args.entrypoint is None:
        bootstrap.validate()
    else:
        bootstrap.validate(load_app_factory(args.entrypoint))
    print("配置有效: %s" % path)
    return 0


def _plugins_list(args: argparse.Namespace) -> int:
    del args
    bootstrap = PluginBootstrap(Path("config.yaml").resolve())
    catalog = bootstrap.discover()
    candidates = catalog.candidates
    settings = bootstrap.settings
    loaded = {item.descriptor.plugin_id: item for item in catalog.plugins}
    selected = set(settings.enabled)
    if settings.local is not None and settings.local.auto_enable:
        selected.update(
            candidate.plugin_id
            for candidate in candidates
            if candidate.origin.kind == "directory"
        )

    print("ID\tVERSION\tORIGIN\tSELECTED\tCORE\tDEPENDENCIES\tLOCATION")
    for candidate in candidates:
        loaded_plugin = loaded.get(candidate.plugin_id)
        descriptor = (
            loaded_plugin.descriptor
            if loaded_plugin is not None
            else candidate.descriptor
        )
        version = descriptor.version if descriptor is not None else "<load required>"
        if loaded_plugin is not None:
            core_compatibility = "compatible"
            dependencies = "ready"
        elif descriptor is not None:
            core_compatibility = (
                "compatible"
                if descriptor.supports_core(__version__)
                else "incompatible"
            )
            dependencies = "unselected"
        else:
            core_compatibility = "deferred"
            dependencies = "deferred"
        print(
            "%s\t%s\t%s\t%s\t%s\t%s\t%s"
            % (
                candidate.plugin_id,
                version,
                candidate.origin.kind,
                "yes" if candidate.plugin_id in selected else "no",
                core_compatibility,
                dependencies,
                candidate.origin.location,
            )
        )
    return 0


def _plugins_init(args: argparse.Namespace) -> int:
    descriptor = PluginDescriptor(
        plugin_id=args.plugin_id,
        version="0.1.0",
        requires_core=">=3.1.0.dev2,<4",
    )
    plugin_root = Path(args.path).resolve()
    target = plugin_root / descriptor.plugin_id
    if target.exists():
        raise CliError("插件目录已存在，拒绝覆盖: %s" % target)

    target.mkdir(parents=True)
    (target / "plugin.toml").write_text(
        "schema_version = 1\n"
        f'plugin_id = "{descriptor.plugin_id}"\n'
        f'version = "{descriptor.version}"\n'
        f'requires_core = "{descriptor.requires_core}"\n'
        'entry = "plugin.py"\n'
        "requires_plugins = []\n"
        "provides = []\n"
        "requires_distributions = []\n",
        encoding="utf-8",
    )
    (target / "plugin.py").write_text(
        "from butterbot.plugin import ButterPlugin\n"
        "\n"
        "\n"
        "class Plugin(ButterPlugin):\n"
        "        pass\n"
        "\n",
        encoding="utf-8",
    )
    print("已创建本地插件: %s" % target)
    return 0


def _run(args: argparse.Namespace) -> int:
    working_directory = Path.cwd()
    store = _state_store(working_directory)
    existing = store.refresh()
    if existing is not None and existing.status == "paused":
        return _resume_paused_process(store, existing)
    if args.background:
        pid = _spawn_background(
            entrypoint=args.entrypoint,
            debug=args.debug,
            working_directory=working_directory,
        )
        print("ButterBot 已在后台启动（PID %s）" % pid)
        return 0

    # 先保持旧入口错误优先级；模块只解析一次，后续 import 会命中缓存。
    resolve_entrypoint(args.entrypoint)
    bootstrap = PluginBootstrap()
    if bootstrap.settings.requires_plugin_bootstrap:
        app = bootstrap.build(load_app_factory(args.entrypoint))
    else:
        app = load_app(args.entrypoint)
    state = RuntimeState.running(
        pid=os.getpid(),
        entrypoint=args.entrypoint,
        debug=args.debug,
        working_directory=str(working_directory),
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
        print("ButterBot 已暂停（PID %s，入口 %s）" % (state.pid, state.entrypoint))
        return 0
    if is_process_alive(state):
        print("ButterBot 正在运行（PID %s，入口 %s）" % (state.pid, state.entrypoint))
        return 0
    print("ButterBot 已停止（入口 %s）" % state.entrypoint)
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
    print("ButterBot 已关闭（入口 %s）" % state.entrypoint)
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
        entrypoint=state.entrypoint,
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
    entrypoint: str,
    debug: bool,
    working_directory: Path,
) -> int:
    store = _state_store(working_directory)
    existing = store.refresh()
    if existing is not None and is_process_alive(existing):
        raise CliError("已有 ButterBot 实例正在运行（PID %s）" % existing.pid)

    command = [sys.executable, "-m", "butterbot.cli", "run", entrypoint]
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


def _resume_paused_process(store: StateStore, state: RuntimeState) -> int:
    if state.pid is None or not is_process_alive(state):
        store.mark_stopped(state.token, state.exit_code)
        raise CliError("暂停的 ButterBot 进程已经退出")
    _resume_process(store, state)
    print(
        "检测到暂停的实例，已恢复原进程（PID %s，入口 %s）；"
        "未创建新实例，如需新实例请使用 restart，或先 close 再 run"
        % (state.pid, state.entrypoint)
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
