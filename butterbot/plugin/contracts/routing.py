from __future__ import annotations

import re
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from butterbot.core.event import Event
from butterbot.core.types import BaseType

if TYPE_CHECKING:
    from butterbot.core.filter import BaseFilter


@dataclass(frozen=True, slots=True)
class SourceRef:
    """事件源实例的逻辑引用.

    ``source_kind`` 标识事件能力类型，``config_key`` 区分同类 Source 的配置实例。
    UUID 仍是 EventBus 的运行时路由键；SourceRef 只用于注册期解析。
    """

    source_kind: str
    config_key: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_kind, str)
            or not self.source_kind
            or self.source_kind != self.source_kind.strip()
        ):
            raise ValueError("source_kind 必须是非空且无首尾空白的字符串")
        if self.config_key is not None and (
            not isinstance(self.config_key, str)
            or not self.config_key
            or self.config_key != self.config_key.strip()
        ):
            raise ValueError("config_key 必须为 None 或非空且无首尾空白的字符串")


@dataclass(frozen=True, slots=True)
class SubscriptionSpec:
    """一个待解析的逻辑订阅声明."""

    source: SourceRef
    status: str | re.Pattern[str] | BaseType
    callback: Callable[[Event], Coroutine[Any, Any, None]]
    event_filter: BaseFilter | None = None
    allow_multiple: bool = False


__all__ = ["SourceRef", "SubscriptionSpec"]
