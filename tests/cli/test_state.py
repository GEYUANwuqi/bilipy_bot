"""CLI 状态文件测试."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest

from butterbot.cli.errors import CliError
from butterbot.cli.state import (
    RuntimeHealth,
    RuntimeState,
    StateStore,
    is_process_alive,
)


def _running_state(tmp_path: Path, *, pid: int | None = None) -> RuntimeState:
    return RuntimeState.running(
        pid=pid or os.getpid(),
        debug=False,
        working_directory=str(tmp_path),
        application_path="example.app",
        config_path=str(tmp_path / "config.yaml"),
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
        "schema_version": 4,
        "token": "token",
        "status": "running",
        "pid": pid,
        "process_identity": None,
        "debug": False,
        "working_directory": str(tmp_path),
        "application_path": "example.app",
        "config_path": str(tmp_path / "config.yaml"),
        "log_file": str(tmp_path / "app.log"),
        "started_at": 1.0,
        "health": {
            "state": "starting",
            "observed_at": 1.0,
            "source_total": 0,
            "source_ready": 0,
            "source_degraded": 0,
            "plugin_total": 0,
            "plugin_unhealthy": 0,
            "failure_types": [],
        },
        "stopped_at": None,
        "exit_code": None,
    }
    store.path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(CliError, match="PID 无效"):
        store.load()


def test_update_health_is_persisted_and_token_scoped(tmp_path: Path):
    store = StateStore(tmp_path / "runtime.json")
    state = _running_state(tmp_path)
    store.claim(state)
    health = RuntimeHealth(
        state="degraded",
        observed_at=2.0,
        source_total=2,
        source_ready=1,
        source_degraded=1,
        plugin_total=1,
        plugin_unhealthy=1,
        failure_types=("ConnectionError",),
    )

    assert store.update_health("wrong-token", health) == state
    updated = store.update_health(state.token, health)

    assert updated is not None
    assert updated.health == health
    assert store.load(required=True) == updated


def test_schema_v3_state_is_migrated_with_starting_health(tmp_path: Path):
    store = StateStore(tmp_path / "runtime.json")
    payload = asdict(_running_state(tmp_path))
    payload["schema_version"] = 3
    payload.pop("health")
    store.path.write_text(json.dumps(payload), encoding="utf-8")

    migrated = store.load(required=True)

    assert migrated is not None
    assert migrated.schema_version == 4
    assert migrated.health.state == "starting"
