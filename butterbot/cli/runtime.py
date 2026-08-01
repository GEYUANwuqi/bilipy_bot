"""CLI 应用运行与本地进程管理操作."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import click

from butterbot.app import AppHealth, BotApp

from .errors import CliError
from .loader import load_application
from .state import RuntimeHealth, RuntimeState, StateStore, is_process_alive

_STATE_DIRECTORY = ".butterbot"
_STATE_FILENAME = "runtime.json"
_LOG_FILENAME = "butterbot.log"
_STOP_TIMEOUT = 10.0
_BACKGROUND_START_TIMEOUT = 5.0
_BACKGROUND_CLEANUP_TIMEOUT = 2.0
_HEALTH_STALE_SECONDS = 5.0
_STATUS_NOT_RUNNING = 3
_DEFAULT_APPLICATION_PATH = "app.app"


def run_application(
    *,
    application: str | None,
    application_override: str | None,
    config_path: Path | None,
    background: bool,
    debug: bool,
) -> int:
    """构建应用，并在前台运行或委托给后台子进程.

    约定：新项目统一使用工厂入口注入配置；不指定 ``-config`` 时仍兼容
    ``app = BotApp()`` 对象入口。
    """
    from butterbot.plugin import PluginBootstrap

    working_directory = Path.cwd()
    application_path = application_override or application or _DEFAULT_APPLICATION_PATH
    config_specified = config_path is not None
    resolved_config_path = (config_path or Path("config.yaml")).resolve()
    store = _state_store(working_directory)
    if background:
        pid = _spawn_background(
            application_path=application_path,
            config_path=resolved_config_path if config_specified else None,
            debug=debug,
            working_directory=working_directory,
        )
        click.echo("ButterBot 已在后台启动（PID %s）" % pid)
        return 0

    application_entry = load_application(application_path)
    if config_specified and isinstance(application_entry, BotApp):
        raise CliError(
            "指定 -config 时必须使用工厂入口注入配置；"
            "请把入口 '%s' 改为 app = BotApp 或 def app(*, config, source_factory_registry)"
            % application_path
        )
    bootstrap = PluginBootstrap(resolved_config_path)
    app = bootstrap.build(application_entry)
    state = RuntimeState.running(
        pid=os.getpid(),
        debug=debug,
        working_directory=str(working_directory),
        application_path=application_path,
        config_path=str(resolved_config_path),
        log_file=str(_log_file(working_directory)),
    )
    store.claim(state)

    exit_code = 1

    def report_health(health: AppHealth) -> None:
        store.update_health(state.token, _runtime_health(health))

    try:
        app.run(health_reporter=report_health)
        exit_code = 0
        return 0
    finally:
        store.mark_stopped(state.token, exit_code)


def show_status() -> int:
    """显示当前工作目录登记的应用状态."""
    state = _state_store(Path.cwd()).refresh()
    if state is None:
        click.echo("ButterBot 未登记")
        return _STATUS_NOT_RUNNING
    if is_process_alive(state):
        if state.legacy_suspended:
            click.echo(
                "ButterBot 仍处于旧版本暂停状态（PID %s）；"
                "请执行 stop 完成优雅停止" % state.pid
            )
            return 1
        health = state.health
        source_summary = "Source %s/%s ready" % (
            health.source_ready,
            health.source_total,
        )
        plugin_summary = "Plugin %s/%s healthy" % (
            health.plugin_total - health.plugin_unhealthy,
            health.plugin_total,
        )
        if health.state == "starting":
            if time.time() - health.observed_at > _HEALTH_STALE_SECONDS:
                click.echo(
                    "ButterBot 运行降级（PID %s；健康报告已超过 %.0f 秒未更新）"
                    % (state.pid, _HEALTH_STALE_SECONDS)
                )
                return 1
            click.echo("ButterBot 正在启动（PID %s）" % state.pid)
            return 0
        if health.state == "ready":
            if time.time() - health.observed_at > _HEALTH_STALE_SECONDS:
                click.echo(
                    "ButterBot 运行降级（PID %s；%s；%s；"
                    "失败 HealthReportStale）"
                    % (state.pid, source_summary, plugin_summary)
                )
                return 1
            click.echo(
                "ButterBot 已就绪（PID %s；%s；%s）"
                % (state.pid, source_summary, plugin_summary)
            )
            return 0
        if health.state == "stopping":
            click.echo("ButterBot 正在停止（PID %s）" % state.pid)
            return 0
        failures = ", ".join(health.failure_types) or "无结构化异常"
        click.echo(
            "ButterBot 运行降级（PID %s；%s；%s；失败 %s）"
            % (state.pid, source_summary, plugin_summary, failures)
        )
        return 1
    click.echo("ButterBot 已停止")
    return _STATUS_NOT_RUNNING


def stop_application() -> int:
    """向受管进程发送 SIGTERM 并等待应用生命周期清理."""
    state = _stop_managed_process(_state_store(Path.cwd()))
    click.echo("ButterBot 已停止（配置 %s）" % state.config_path)
    return 0


def close_application() -> int:
    """兼容旧命令；关闭行为与 :func:`stop_application` 完全一致."""
    return stop_application()


def restart_application() -> int:
    """使用原入口和配置完整重启应用."""
    store = _state_store(Path.cwd())
    state = store.refresh()
    if state is None:
        raise CliError("没有可重启的应用记录")
    if is_process_alive(state):
        _stop_managed_process(store)

    # 必须等旧 PID 完全消失后才创建新解释器，不复用任何运行时对象。
    default_config_path = (Path(state.working_directory) / "config.yaml").resolve()
    pid = _spawn_background(
        application_path=state.application_path,
        config_path=(
            None
            if Path(state.config_path).resolve() == default_config_path
            else Path(state.config_path)
        ),
        debug=state.debug,
        working_directory=Path(state.working_directory),
    )
    click.echo("ButterBot 已完整重启（PID %s）" % pid)
    return 0


def _stop_managed_process(store: StateStore) -> RuntimeState:
    state = store.refresh()
    if state is None:
        raise CliError("没有找到运行状态: %s" % store.path)
    if not is_process_alive(state) or state.pid is None:
        raise CliError("ButterBot 当前未运行", exit_code=_STATUS_NOT_RUNNING)

    if state.legacy_suspended:
        _continue_process(state.pid)
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
    config_path: Path | None,
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
    ]
    if config_path is not None:
        command.extend(["-config", str(config_path)])
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
            _cleanup_background_process(process)
            raise CliError(
                "ButterBot 后台启动失败（退出码 %s），请检查日志 %s"
                % (return_code, log_file)
            )
        state = store.load()
        if state is not None and state.pid == process.pid and is_process_alive(state):
            return process.pid
        time.sleep(0.05)

    _cleanup_background_process(process)
    raise CliError("等待 ButterBot 后台进程登记状态超时")


def _cleanup_background_process(process: subprocess.Popen[bytes]) -> None:
    """回收启动失败的独立进程组，超时后升级到 SIGKILL."""
    _signal_background_process(process, signal.SIGTERM)
    leader_exited = False
    try:
        process.wait(timeout=_BACKGROUND_CLEANUP_TIMEOUT)
        leader_exited = True
    except subprocess.TimeoutExpired:
        pass

    # 即使主进程已经退出，独立进程组中仍可能留下它创建的子进程；POSIX 下继续
    # 对同一受管进程组发送 SIGKILL，进程组不存在时会安静返回。
    kill_signal = getattr(signal, "SIGKILL", None)
    if kill_signal is None:
        if not leader_exited:
            try:
                process.kill()
            except ProcessLookupError:
                pass
    else:
        _signal_background_process(process, kill_signal)
    if leader_exited:
        return
    try:
        process.wait(timeout=_BACKGROUND_CLEANUP_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise CliError(
            "后台启动失败且无法回收子进程组（PID %s）" % process.pid
        ) from exc


def _signal_background_process(
    process: subprocess.Popen[bytes],
    process_signal: signal.Signals,
) -> None:
    """只向由 ``start_new_session`` 创建的受管进程组发信号."""
    try:
        os.killpg(process.pid, process_signal)
    except ProcessLookupError:
        return
    except (AttributeError, NotImplementedError):
        try:
            process.send_signal(process_signal)
        except ProcessLookupError:
            pass


def _state_store(working_directory: Path) -> StateStore:
    return StateStore(working_directory / _STATE_DIRECTORY / _STATE_FILENAME)


def _log_file(working_directory: Path) -> Path:
    return (working_directory / _STATE_DIRECTORY / _LOG_FILENAME).resolve()


def _runtime_health(health: AppHealth) -> RuntimeHealth:
    """把进程内快照压缩为不含配置和异常消息的 CLI 摘要."""
    source_ready = sum(source.healthy for source in health.sources)
    source_degraded = sum(not source.healthy for source in health.sources)
    plugin_unhealthy = sum(not plugin.healthy for plugin in health.plugins)
    failure_types = tuple(
        source.last_error_type
        for source in health.sources
        if source.last_error_type is not None
    ) + tuple(
        failure_type
        for plugin in health.plugins
        for failure_type in plugin.failure_types
    )
    return RuntimeHealth(
        state=health.state.value,
        observed_at=health.observed_at,
        source_total=len(health.sources),
        source_ready=source_ready,
        source_degraded=source_degraded,
        plugin_total=len(health.plugins),
        plugin_unhealthy=plugin_unhealthy,
        failure_types=failure_types,
    )


def _continue_process(pid: int) -> None:
    continue_signal = getattr(signal, "SIGCONT", None)
    if continue_signal is None:
        raise CliError("当前平台无法恢复旧版本暂停的进程")
    try:
        os.kill(pid, continue_signal)
    except ProcessLookupError:
        raise CliError("旧版本暂停的 ButterBot 进程已经退出") from None
    except PermissionError as exc:
        raise CliError("没有权限恢复旧版本 ButterBot 进程（PID %s）" % pid) from exc


__all__ = [
    "close_application",
    "restart_application",
    "run_application",
    "show_status",
    "stop_application",
]
