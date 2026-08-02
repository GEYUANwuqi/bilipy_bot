from __future__ import annotations

import re
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from butterbot.core.event import Event
from butterbot.core.routing import SourceRef
from butterbot.core.types import BaseType

if TYPE_CHECKING:
    from butterbot.core.filter import BaseFilter


@dataclass(frozen=True, slots=True)
class SubscriptionSpec:
    """一个待解析的逻辑订阅声明."""

    source: SourceRef
    status: str | re.Pattern[str] | BaseType
    callback: Callable[[Event], Coroutine[Any, Any, None]]
    event_filter: BaseFilter | None = None
    allow_multiple: bool = False


__all__ = ["SourceRef", "SubscriptionSpec"]
