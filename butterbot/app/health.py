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
class AppHealth:
    """应用、Source 和插件的一致性健康快照."""

    state: AppHealthState
    observed_at: float
    sources: tuple[SourceDiagnostic, ...]
    plugins: tuple[PluginDiagnostic, ...]

    @property
    def healthy(self) -> bool:
        return self.state is AppHealthState.READY
