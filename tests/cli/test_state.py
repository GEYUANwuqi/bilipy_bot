"""CLI 状态文件测试."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from butterbot.cli.errors import CliError
from butterbot.cli.state import RuntimeState, StateStore, is_process_alive


def _running_state(tmp_path: Path, *, pid: int | None = None) -> RuntimeState:
    return RuntimeState.running(
        pid=pid or os.getpid(),
        entrypoint="example:app",
        debug=False,
        working_directory=str(tmp_path),
        log_file=str(tmp_path / "app.log"),
    )


def test_claim_load_and_mark_stopped(tmp_path: Path):
    store = StateStore(tmp_path / "runtime.json")
    state = _running_state(tmp_path)

    store.claim(state)
    loaded = store.load(required=True)
    assert loaded is not None
    assert loaded == state
    assert is_process_alive(loaded)

    paused = store.mark_paused(state.token)
    assert paused is not None
    assert paused.status == "paused"
    assert paused.pid == state.pid
    assert is_process_alive(paused)

    running = store.mark_running(state.token)
    assert running is not None
    assert running.status == "running"

    stopped = store.mark_stopped(state.token, 0)
    assert stopped is not None
    assert stopped.status == "stopped"
    assert stopped.pid is None
    assert stopped.exit_code == 0


def test_claim_rejects_live_process(tmp_path: Path):
    store = StateStore(tmp_path / "runtime.json")
    store.claim(_running_state(tmp_path))

    with pytest.raises(CliError, match="正在运行"):
        store.claim(_running_state(tmp_path))


def test_claim_replaces_stale_process(tmp_path: Path):
    store = StateStore(tmp_path / "runtime.json")
    stale = _running_state(tmp_path, pid=999_999_999)
    replacement = _running_state(tmp_path)

    store.claim(stale)
    store.claim(replacement)

    assert store.load(required=True) == replacement


def test_required_state_reports_missing_file(tmp_path: Path):
    store = StateStore(tmp_path / "missing.json")

    with pytest.raises(CliError, match="没有找到运行状态"):
        store.load(required=True)


@pytest.mark.parametrize("pid", [0, -1, True, "123"])
def test_rejects_invalid_running_pid(tmp_path: Path, pid: object):
    store = StateStore(tmp_path / "runtime.json")
    data = {
        "schema_version": 2,
        "token": "token",
        "status": "running",
        "pid": pid,
        "process_identity": None,
        "entrypoint": "example:app",
        "debug": False,
        "working_directory": str(tmp_path),
        "log_file": str(tmp_path / "app.log"),
        "started_at": 1.0,
        "stopped_at": None,
        "exit_code": None,
    }
    store.path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(CliError, match="PID 无效"):
        store.load()
