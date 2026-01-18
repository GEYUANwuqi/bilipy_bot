from dataclasses import dataclass
from typing import Generic
from utils import BaseType
from bili_data import BaseDataT


@dataclass
class Event(Generic[BaseDataT]):
    """事件类，包含数据和状态.

    Attributes:
        data: 事件数据
        status: 事件状态

    Usage:
        # 创建动态事件
        from event import DynamicData
        from utils import DynamicType
        event = Event(data=dynamic_data, status=DynamicType.NEW)

        # 创建直播事件
        from event import LiveRoomData
        from utils import LiveType
        event = Event(data=live_data, status=LiveType.OPEN)
    """
    data: BaseDataT
    status: BaseType

    def __repr__(self) -> str:
        return f"Event(data={self.data}, status={self.status})"

    def __str__(self) -> str:
        return self.__repr__()