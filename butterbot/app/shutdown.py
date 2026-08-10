"""应用退出请求的稳定公开模型."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ShutdownAction(StrEnum):
    """宿主在应用完成清理后应执行的动作."""

    STOP = "stop"
    RESTART = "restart"


@dataclass(frozen=True, slots=True)
class ShutdownRequest:
    """一次不可变且不包含敏感信息的应用退出请求."""

    action: ShutdownAction
    requested_at: float
    requested_by: str
    reason: str | None = None


__all__ = ["ShutdownAction", "ShutdownRequest"]
