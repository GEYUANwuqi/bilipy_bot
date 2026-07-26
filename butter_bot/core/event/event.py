from dataclasses import dataclass, field
from typing import Generic
from uuid import uuid4

from butter_bot.core.data import BaseDataT
from butter_bot.core.types import BaseType


@dataclass
class Event(Generic[BaseDataT]):
    """事件类，包含数据和状态.

    Attributes:
        data: 事件数据
        status: 事件状态
        id: 事件唯一标识符
    """

    data: BaseDataT
    status: BaseType
    id: str = field(default_factory=lambda: str(uuid4()))

    def __repr__(self) -> str:
        return "Event(data=%s, status=%s)" % (self.data, self.status)

    def __str__(self) -> str:
        return self.__repr__()
