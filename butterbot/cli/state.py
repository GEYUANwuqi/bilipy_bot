"""CLI 本地进程状态持久化."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterator, Literal
from uuid import uuid4

from .errors import CliError

_STATE_SCHEMA_VERSION = 4
_LOCK_STALE_SECONDS = 30.0
_LOCK_WAIT_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class RuntimeHealth:
    """CLI 状态文件中的非敏感健康摘要."""

    state: Literal["starting", "ready", "degraded", "stopping", "stopped"]
    observed_at: float
    source_total: int = 0
    source_ready: int = 0
    source_degraded: int = 0
    plugin_total: int = 0
    plugin_unhealthy: int = 0
    failure_types: tuple[str, ...] = ()

    @classmethod
    def starting(cls) -> RuntimeHealth:
        return cls(state="starting", observed_at=time.time())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeHealth:
        payload = dict(data)
        failure_types = payload.get("failure_types", ())
        if not isinstance(failure_types, (list, tuple)) or not all(
            isinstance(item, str) and item for item in failure_types
        ):
            raise CliError("CLI 健康状态结构无效")
        payload["failure_types"] = tuple(failure_types)
        try:
            health = cls(**payload)
        except (TypeError, ValueError) as exc:
            raise CliError("CLI 健康状态结构无效") from exc
        health._validate()
        return health

    def _validate(self) -> None:
        if self.state not in (
            "starting",
            "ready",
            "degraded",
            "stopping",
            "stopped",
        ) or not isinstance(self.observed_at, (int, float)):
            raise CliError("CLI 健康状态结构无效")
        counts = (
            self.source_total,
            self.source_ready,
            self.source_degraded,
            self.plugin_total,
            self.plugin_unhealthy,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in counts
        ):
            raise CliError("CLI 健康状态结构无效")
        if (
            self.source_ready > self.source_total
            or self.source_degraded > self.source_total
            or self.plugin_unhealthy > self.plugin_total
        ):
            raise CliError("CLI 健康状态结构无效")


@dataclass(frozen=True, slots=True)
class RuntimeState:
    """一次受 CLI 管理的应用运行记录."""

    schema_version: int
    token: str
    status: Literal["running", "paused", "stopped"]
    pid: int | None
    process_identity: str | None
    debug: bool
    working_directory: str
    application_path: str
    config_path: str
    log_file: str
    started_at: float
    health: RuntimeHealth
    stopped_at: float | None = None
    exit_code: int | None = None

    @classmethod
    def running(
        cls,
        *,
        pid: int,
        debug: bool,
        working_directory: str,
        application_path: str,
        config_path: str,
        log_file: str,
    ) -> RuntimeState:
        return cls(
            schema_version=_STATE_SCHEMA_VERSION,
            token=uuid4().hex,
            status="running",
            pid=pid,
            process_identity=process_identity(pid),
            debug=debug,
            working_directory=working_directory,
            application_path=application_path,
            config_path=config_path,
            log_file=log_file,
            started_at=time.time(),
            health=RuntimeHealth.starting(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeState:
        payload = dict(data)
        schema_version = payload.get("schema_version")
        if schema_version == 3 and "health" not in payload:
            # v3 只有 PID liveness；升级后保留运行记录，并从
            # starting 开始等待新进程上报，避免要求用户手删状态文件。
            migrated_state = (
                "stopped" if payload.get("status") == "stopped" else "starting"
            )
            payload["schema_version"] = _STATE_SCHEMA_VERSION
            payload["health"] = asdict(
                RuntimeHealth(state=migrated_state, observed_at=time.time())
            )
        elif schema_version != _STATE_SCHEMA_VERSION:
            raise CliError("不支持的 CLI 状态文件版本: %s" % schema_version)
        try:
            health_data = payload.get("health")
            if not isinstance(health_data, dict):
                raise TypeError("health must be a mapping")
            payload["health"] = RuntimeHealth.from_dict(health_data)
            state = cls(**payload)
        except (TypeError, ValueError) as exc:
            raise CliError("CLI 状态文件结构无效") from exc
        state._validate()
        return state

    def _validate(self) -> None:
        string_fields = {
            "token": self.token,
            "working_directory": self.working_directory,
            "application_path": self.application_path,
            "config_path": self.config_path,
            "log_file": self.log_file,
        }
        if any(
            not isinstance(value, str) or not value for value in string_fields.values()
        ):
            raise CliError("CLI 状态文件结构无效")
        if not isinstance(self.debug, bool):
            raise CliError("CLI 状态文件结构无效")
        if self.status not in ("running", "paused", "stopped"):
            raise CliError("CLI 状态文件结构无效")
        if not isinstance(self.started_at, (int, float)):
            raise CliError("CLI 状态文件结构无效")
        if not isinstance(self.health, RuntimeHealth):
            raise CliError("CLI 状态文件结构无效")
        if self.stopped_at is not None and not isinstance(
            self.stopped_at, (int, float)
        ):
            raise CliError("CLI 状态文件结构无效")
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise CliError("CLI 状态文件结构无效")

        if self.status in ("running", "paused"):
            if (
                isinstance(self.pid, bool)
                or not isinstance(self.pid, int)
                or self.pid <= 0
            ):
                raise CliError("CLI 状态文件中的运行 PID 无效")
        elif self.pid is not None or self.process_identity is not None:
            raise CliError("CLI 状态文件中的停止状态无效")


class StateStore:
    """原子读写一个应用实例的运行状态."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self._lock_path = self.path.with_name(self.path.name + ".lock")

    def load(self, *, required: bool = False) -> RuntimeState | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            if required:
                raise CliError("没有找到运行状态: %s" % self.path) from None
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise CliError("无法读取 CLI 状态文件: %s" % self.path) from exc
        if not isinstance(data, dict):
            raise CliError("CLI 状态文件结构无效")
        return RuntimeState.from_dict(data)

    def claim(self, state: RuntimeState) -> None:
        """登记运行中实例；已有存活实例时拒绝覆盖."""
        with self._lock():
            existing = self._load_unlocked()
            if existing is not None and is_process_alive(existing):
                raise CliError("已有 ButterBot 实例正在运行（PID %s）" % existing.pid)
            self._write_unlocked(state)

    def mark_paused(self, token: str) -> RuntimeState | None:
        """仅由持有相同 token 的进程记录暂停状态."""
        return self._mark_active_status(token, "paused")

    def mark_running(self, token: str) -> RuntimeState | None:
        """仅由持有相同 token 的进程记录恢复运行."""
        return self._mark_active_status(token, "running")

    def mark_stopped(self, token: str, exit_code: int | None) -> RuntimeState | None:
        """仅由持有相同 token 的进程把记录标记为停止."""
        with self._lock():
            state = self._load_unlocked()
            if state is None or state.token != token:
                return state
            stopped = replace(
                state,
                status="stopped",
                pid=None,
                process_identity=None,
                stopped_at=time.time(),
                exit_code=exit_code,
                health=replace(
                    state.health,
                    state="stopped",
                    observed_at=time.time(),
                ),
            )
            self._write_unlocked(stopped)
            return stopped

    def update_health(
        self,
        token: str,
        health: RuntimeHealth,
    ) -> RuntimeState | None:
        """由当前运行实例原子更新健康摘要."""
        health._validate()
        with self._lock():
            state = self._load_unlocked()
            if state is None or state.token != token or state.status == "stopped":
                return state
            updated = replace(state, health=health)
            self._write_unlocked(updated)
            return updated

    def refresh(self) -> RuntimeState | None:
        """清理已经退出但仍标记为 running 的陈旧状态."""
        state = self.load()
        if state is None or state.status == "stopped" or is_process_alive(state):
            return state
        return self.mark_stopped(state.token, state.exit_code)

    def _mark_active_status(
        self,
        token: str,
        status: Literal["running", "paused"],
    ) -> RuntimeState | None:
        with self._lock():
            state = self._load_unlocked()
            if state is None or state.token != token or state.pid is None:
                return state
            updated = replace(state, status=status)
            self._write_unlocked(updated)
            return updated

    def _load_unlocked(self) -> RuntimeState | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise CliError("无法读取 CLI 状态文件: %s" % self.path) from exc
        if not isinstance(data, dict):
            raise CliError("CLI 状态文件结构无效")
        return RuntimeState.from_dict(data)

    def _write_unlocked(self, state: RuntimeState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name("%s.%s.tmp" % (self.path.name, uuid4().hex))
        try:
            temporary.write_text(
                json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        except OSError as exc:
            raise CliError("无法写入 CLI 状态文件: %s" % self.path) from exc
        finally:
            try:
                temporary.unlink()
            except OSError:
                pass

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + _LOCK_WAIT_SECONDS
        while True:
            try:
                self._lock_path.mkdir()
                break
            except FileExistsError:
                try:
                    age = time.time() - self._lock_path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > _LOCK_STALE_SECONDS:
                    try:
                        self._lock_path.rmdir()
                    except (FileNotFoundError, OSError):
                        pass
                    continue
                if time.monotonic() >= deadline:
                    raise CliError("CLI 状态文件正被其他命令占用")
                time.sleep(0.02)
        try:
            yield
        finally:
            try:
                self._lock_path.rmdir()
            except FileNotFoundError:
                pass


def is_process_alive(state: RuntimeState) -> bool:
    if state.status == "stopped" or state.pid is None:
        return False
    try:
        os.kill(state.pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

    if state.process_identity is None:
        return True
    return process_identity(state.pid) == state.process_identity


def process_identity(pid: int) -> str | None:
    """读取 Linux 进程启动时钟，避免误操作复用后的 PID."""
    stat_path = Path("/proc") / str(pid) / "stat"
    try:
        stat = stat_path.read_text(encoding="utf-8")
    except OSError:
        return None
    closing_parenthesis = stat.rfind(")")
    if closing_parenthesis < 0:
        return None
    fields = stat[closing_parenthesis + 2 :].split()
    if len(fields) <= 19:
        return None
    return fields[19]
