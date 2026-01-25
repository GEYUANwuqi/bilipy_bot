from dataclasses import dataclass
from typing import Generic, TypeVar, Optional
from bili_data import LiveRoomData, DynamicData, BaseDataT
from utils import DynamicType, LiveType
from typing import Literal
from copy import copy


@dataclass
class DataPair(Generic[BaseDataT]):
    """存储新旧数据对"""
    old: Optional[BaseDataT] = None
    new: Optional[BaseDataT] = None

    def update(self, new_data: BaseDataT):
        """更新数据"""
        if self.old is None:
            self.old = new_data
            self.new = new_data
        else:
            self.old = self.new
            self.new = new_data

    def get_data(self, value: Literal["old", "new"]) -> BaseDataT:
        """获取数据浅拷贝"""
        data = getattr(self, value)
        return copy(data)


def get_dynamic_status(
    data_pair: DataPair[DynamicData]
) -> DynamicType:
    """判断动态状态.
    Args:
        data_pair (DataPair[DynamicData]): 动态数据对

    Returns:
        DynamicType: 当前的动态状态
    """

    old_timestamp = data_pair.old.pub_ts
    new_timestamp = data_pair.new.pub_ts
    # 新动态的时间戳大于旧动态，说明有新动态
    if new_timestamp > old_timestamp:
        return DynamicType.NEW
    # 新动态的时间戳早于旧动态，说明动态被删除
    elif new_timestamp < old_timestamp:
        return DynamicType.DELETED
    # 时间戳相同，没有变化
    else:
        return DynamicType.NULL


def get_live_status(
    data_pair: DataPair[LiveRoomData]
) -> LiveType:
    """判断直播状态.
    Args:
        data_pair (DataPair[LiveRoomData]): 直播数据对

    Returns:
        LiveType: 当前的直播状态
    """

    old_status = data_pair.old.room_info.live_status
    new_status = data_pair.new.room_info.live_status
    # 刚开播：旧状态不是直播中(0或2)，新状态是直播中(1)
    if old_status != 1 and new_status == 1:
        return LiveType.OPEN
    # 刚下播：旧状态是直播中(1)，新状态不是直播中(0或2)
    elif old_status == 1 and new_status != 1:
        return LiveType.CLOSE
    # 直播中：新旧状态都是直播中(1)
    elif old_status == 1 and new_status == 1:
        return LiveType.ONLINE
    # 未开播：其他情况(包括一直未开播、轮播等状态)
    else:
        return LiveType.OFFLINE
