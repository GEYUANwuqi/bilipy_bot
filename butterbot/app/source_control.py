"""插件可用的声明事件源运行期控制面."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from butterbot.core.source import BaseSource

if TYPE_CHECKING:
    from .bot_app import BotApp


@dataclass(frozen=True, slots=True)
class DeclaredSourceRef:
    """YAML 中一个 ``config_key + factory_id`` 声明的稳定引用."""

    config_key: str
    factory_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("config_key", self.config_key),
            ("factory_id", self.factory_id),
        ):
            if not value or value != value.strip():
                raise ValueError("%s 必须是非空且无首尾空白的字符串" % name)


@dataclass(frozen=True, slots=True)
class DeclaredSourceDiagnostic:
    """声明 Source 是否已实例化及其当前状态."""

    reference: DeclaredSourceRef
    source_name: str
    source_id: UUID | None
    source_kind: str | None
    state: str


class RuntimeSourceController:
    """只允许插件管理 YAML 已声明 Source 的窄控制接口."""

    def __init__(self, app: BotApp) -> None:
        self._app = app

    def declarations(self) -> tuple[DeclaredSourceDiagnostic, ...]:
        """返回全部声明及其实例化状态的稳定快照."""
        return self._app._declared_source_diagnostics()

    async def create(
        self,
        reference: DeclaredSourceRef,
        *,
        start: bool = True,
    ) -> BaseSource:
        """使用原 YAML 参数创建声明 Source，并按需立即启动."""
        return await self._app._create_declared_source(reference, start=start)

    async def start(self, reference: DeclaredSourceRef) -> BaseSource:
        """启动已实例化的声明 Source，重复调用是安全的."""
        return await self._app._start_declared_source(reference)

    async def stop(self, reference: DeclaredSourceRef) -> BaseSource:
        """停止声明 Source，但保留实例和插件订阅."""
        return await self._app._stop_declared_source(reference)

    async def remove(self, reference: DeclaredSourceRef) -> BaseSource | None:
        """停止并删除实例；声明保留，之后可以重新创建."""
        return await self._app._remove_declared_source(reference)


__all__ = [
    "DeclaredSourceDiagnostic",
    "DeclaredSourceRef",
    "RuntimeSourceController",
]
