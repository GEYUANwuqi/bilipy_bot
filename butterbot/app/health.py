"""应用运行时健康快照."""

from dataclasses import dataclass
from enum import StrEnum


class AppHealthState(StrEnum):
    """应用级就绪与健康状态."""

    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPING = "stopping"


@dataclass(frozen=True, slots=True)
class SourceDiagnostic:
    """单个 Source 的可序列化诊断快照."""

    source_id: str
    source_type: str
    source_kind: str | None
    config_key: str
    state: str
    last_success_at: float | None
    last_error_at: float | None
    last_error_type: str | None

    @property
    def healthy(self) -> bool:
        return self.state == "ready"


@dataclass(frozen=True, slots=True)
class PluginDiagnostic:
    """单个插件的非敏感诊断快照."""

    plugin_id: str
    state: str
    failure_types: tuple[str, ...]

    @property
    def healthy(self) -> bool:
        return self.state == "started" and not self.failure_types


@dataclass(frozen=True, slots=True)
class EventBusDiagnostic:
    """事件总线当前负载的非敏感快照."""

    pending_callbacks: int
    max_pending_callbacks: int | None


@dataclass(frozen=True, slots=True)
class TaskDiagnostic:
    """框架托管任务的非敏感诊断信息."""

    owner_type: str
    owner_id: str
    task_name: str
    task_kind: str
    state: str


@dataclass(frozen=True, slots=True)
class PluginRuntimeDiagnostic:
    """插件资源作用域和事件回调的运行时计数."""

    plugin_id: str
    background_tasks: int
    cleanup_callbacks: int
    pending_callbacks: int


@dataclass(frozen=True, slots=True)
class AppHealth:
    """应用、Source 和插件的一致性健康快照."""

    state: AppHealthState
    observed_at: float
    sources: tuple[SourceDiagnostic, ...]
    plugins: tuple[PluginDiagnostic, ...]

    @property
    def healthy(self) -> bool:
        return self.state is AppHealthState.READY


@dataclass(frozen=True, slots=True)
class AppDiagnostics:
    """面向可信插件和宿主的完整只读运行诊断快照.

    快照不包含配置值、异常消息或 traceback，适合经业务权限检查后展示给
    运维人员。详细错误继续只写入日志。
    """

    health: AppHealth
    event_bus: EventBusDiagnostic
    plugin_runtime: tuple[PluginRuntimeDiagnostic, ...]
    tasks: tuple[TaskDiagnostic, ...]
