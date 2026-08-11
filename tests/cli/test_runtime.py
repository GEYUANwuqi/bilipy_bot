"""CLI runtime 分支、信号与后台启动回收测试."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from butterbot.app import (
    AppHealth,
    AppHealthState,
    PluginDiagnostic,
    SourceDiagnostic,
)
from butterbot.cli import runtime
from butterbot.cli.errors import CliError
from butterbot.cli.state import RuntimeHealth, RuntimeState, StateStore


def _state(tmp_path: Path, *, health: RuntimeHealth | None = None) -> RuntimeState:
    state = RuntimeState.running(
        pid=os.getpid(),
        debug=False,
        working_directory=str(tmp_path),
        application_path="app.app",
        config_path=str(tmp_path / "config.yaml"),
        log_file=str(tmp_path / ".butterbot" / "butterbot.log"),
    )
    return replace(state, health=health or state.health)


@pytest.mark.parametrize(
    ("health", "expected_code", "expected_text"),
    [
        (
            RuntimeHealth(state="starting", observed_at=time.time() + 3600),
            0,
            "正在启动",
        ),
        (
            RuntimeHealth(state="starting", observed_at=0),
            1,
            "健康报告已超过",
        ),
        (
            RuntimeHealth(state="ready", observed_at=time.time() + 3600),
            0,
            "已就绪",
        ),
        (
            RuntimeHealth(state="ready", observed_at=0),
            1,
            "HealthReportStale",
        ),
        (RuntimeHealth(state="stopping", observed_at=time.time()), 0, "正在停止"),
    ],
)
def test_status_reports_each_live_health_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    health: RuntimeHealth,
    expected_code: int,
    expected_text: str,
) -> None:
    store = StateStore(tmp_path / ".butterbot" / "runtime.json")
    store.claim(_state(tmp_path, health=health))
    monkeypatch.chdir(tmp_path)

    assert runtime.show_status() == expected_code
    assert expected_text in capsys.readouterr().out


def test_status_reports_legacy_suspended_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = StateStore(tmp_path / ".butterbot" / "runtime.json")
    store.claim(replace(_state(tmp_path), legacy_suspended=True))
    monkeypatch.chdir(tmp_path)

    assert runtime.show_status() == 1
    assert "旧版本暂停状态" in capsys.readouterr().out


class _StopStore:
    def __init__(self, state: RuntimeState | None) -> None:
        self.path = Path("/tmp/runtime.json")
        self.state = state
        self.stopped: list[tuple[str, int | None]] = []

    def refresh(self) -> RuntimeState | None:
        return self.state

    def mark_stopped(
        self,
        token: str,
        exit_code: int | None,
    ) -> RuntimeState | None:
        self.stopped.append((token, exit_code))
        return self.state


def test_stop_managed_process_sends_sigterm_and_marks_stopped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    store = _StopStore(state)
    alive = iter([True, False])
    sent: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(runtime, "is_process_alive", lambda current: next(alive))
    monkeypatch.setattr(runtime.os, "kill", lambda pid, sig: sent.append((pid, sig)))

    result = runtime._stop_managed_process(cast(Any, store))

    assert result is state
    assert sent == [(state.pid, signal.SIGTERM)]
    assert store.stopped == [(state.token, 0)]


def test_stop_managed_process_resumes_legacy_state_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = replace(_state(tmp_path), legacy_suspended=True)
    store = _StopStore(state)
    alive = iter([True, False])
    calls: list[str] = []
    monkeypatch.setattr(runtime, "is_process_alive", lambda current: next(alive))
    monkeypatch.setattr(
        runtime,
        "_continue_process",
        lambda pid: calls.append("continue"),
    )
    monkeypatch.setattr(runtime.os, "kill", lambda pid, sig: calls.append("term"))

    runtime._stop_managed_process(cast(Any, store))

    assert calls == ["continue", "term"]


def test_stop_managed_process_reports_missing_dead_and_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(CliError, match="没有找到运行状态"):
        runtime._stop_managed_process(cast(Any, _StopStore(None)))

    state = _state(tmp_path)
    store = _StopStore(state)
    monkeypatch.setattr(runtime, "is_process_alive", lambda current: False)
    with pytest.raises(CliError, match="当前未运行"):
        runtime._stop_managed_process(cast(Any, store))

    monkeypatch.setattr(runtime, "is_process_alive", lambda current: True)
    monkeypatch.setattr(runtime.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(runtime, "_STOP_TIMEOUT", 0)
    with pytest.raises(CliError, match="优雅关闭超时"):
        runtime._stop_managed_process(cast(Any, store))


@pytest.mark.parametrize(
    ("error", "message", "marked"),
    [
        (ProcessLookupError(), "当前未运行", True),
        (PermissionError(), "没有权限关闭", False),
    ],
)
def test_stop_managed_process_translates_signal_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: BaseException,
    message: str,
    marked: bool,
) -> None:
    state = _state(tmp_path)
    store = _StopStore(state)
    monkeypatch.setattr(runtime, "is_process_alive", lambda current: True)

    def fail_kill(pid: int, process_signal: signal.Signals) -> None:
        raise error

    monkeypatch.setattr(runtime.os, "kill", fail_kill)

    with pytest.raises(CliError, match=message):
        runtime._stop_managed_process(cast(Any, store))

    assert bool(store.stopped) is marked


class _SpawnStore:
    def __init__(self, loaded: RuntimeState | None = None) -> None:
        self.loaded = loaded

    def refresh(self) -> None:
        return None

    def load(self) -> RuntimeState | None:
        return self.loaded


class _FakeProcess:
    def __init__(self, pid: int, return_code: int | None) -> None:
        self.pid = pid
        self.return_code = return_code
        self.wait_calls: list[float] = []

    def poll(self) -> int | None:
        return self.return_code

    def wait(self, timeout: float) -> int:
        self.wait_calls.append(timeout)
        return self.return_code or 0

    def send_signal(self, process_signal: signal.Signals) -> None:
        pass


def test_spawn_background_builds_command_and_returns_registered_pid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid = os.getpid()
    state = _state(tmp_path)
    process = _FakeProcess(pid, None)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(runtime, "_state_store", lambda path: _SpawnStore(state))
    monkeypatch.setattr(runtime, "is_process_alive", lambda current: True)

    def fake_popen(command: list[str], **kwargs: Any) -> _FakeProcess:
        captured["command"] = command
        captured.update(kwargs)
        return process

    monkeypatch.setattr(runtime.subprocess, "Popen", fake_popen)

    result = runtime._spawn_background(
        application_path="custom.app",
        config_path=tmp_path / "deploy.yaml",
        debug=True,
        working_directory=tmp_path,
    )

    assert result == pid
    assert captured["command"][-3:] == [
        "-config",
        str(tmp_path / "deploy.yaml"),
        "--debug",
    ]
    assert "-config" in captured["command"]
    assert captured["start_new_session"] is True


def test_spawn_background_allows_slow_application_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid = os.getpid()
    state = _state(tmp_path)
    process = _FakeProcess(pid, None)
    elapsed = 0.0

    class DelayedStore(_SpawnStore):
        def load(self) -> RuntimeState | None:
            return state if elapsed >= 6.0 else None

    monkeypatch.setattr(runtime, "_state_store", lambda path: DelayedStore())
    monkeypatch.setattr(runtime, "is_process_alive", lambda current: True)
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(runtime, "_cleanup_background_process", lambda current: None)
    monkeypatch.setattr(runtime.time, "monotonic", lambda: elapsed)

    def advance_time(_seconds: float) -> None:
        nonlocal elapsed
        elapsed += 1.0

    monkeypatch.setattr(runtime.time, "sleep", advance_time)

    assert (
        runtime._spawn_background(
            application_path="slow.app",
            config_path=None,
            debug=False,
            working_directory=tmp_path,
        )
        == pid
    )


def test_spawn_background_reports_child_exit_and_spawn_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess(12345, 7)
    monkeypatch.setattr(runtime, "_state_store", lambda path: _SpawnStore())
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(runtime, "_signal_background_process", lambda *args: None)

    with pytest.raises(CliError, match="退出码 7"):
        runtime._spawn_background(
            application_path="broken.app",
            config_path=None,
            debug=False,
            working_directory=tmp_path,
        )
    assert process.wait_calls

    def fail_spawn(*args: Any, **kwargs: Any) -> _FakeProcess:
        raise OSError("spawn failed")

    monkeypatch.setattr(runtime.subprocess, "Popen", fail_spawn)
    with pytest.raises(CliError, match="无法启动"):
        runtime._spawn_background(
            application_path="broken.app",
            config_path=None,
            debug=False,
            working_directory=tmp_path,
        )


def test_cleanup_background_process_escalates_and_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess(12345, None)
    signals: list[signal.Signals] = []
    waits = iter(
        [
            subprocess.TimeoutExpired("child", 0.1),
            subprocess.TimeoutExpired("child", 0.1),
        ]
    )
    monkeypatch.setattr(
        process,
        "wait",
        lambda timeout: (_ for _ in ()).throw(next(waits)),
    )
    monkeypatch.setattr(
        runtime,
        "_signal_background_process",
        lambda current, process_signal: signals.append(process_signal),
    )

    with pytest.raises(CliError, match="无法回收"):
        runtime._cleanup_background_process(cast(Any, process))

    assert signals == [signal.SIGTERM, signal.SIGKILL]


def test_runtime_health_aggregates_sources_and_plugins() -> None:
    health = AppHealth(
        state=AppHealthState.DEGRADED,
        observed_at=10.0,
        sources=(
            SourceDiagnostic("1", "A", None, "a", "ready", 1, None, None),
            SourceDiagnostic(
                "2",
                "B",
                None,
                "b",
                "degraded",
                None,
                2,
                "ConnectionError",
            ),
        ),
        plugins=(
            PluginDiagnostic("ok", "started", ()),
            PluginDiagnostic("bad", "failed", ("TimeoutError",)),
        ),
    )

    result = runtime._runtime_health(health)

    assert result.source_ready == 1
    assert result.source_degraded == 1
    assert result.plugin_unhealthy == 1
    assert result.failure_types == ("ConnectionError", "TimeoutError")
