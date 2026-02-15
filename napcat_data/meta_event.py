from dataclasses import dataclass
from typing import Optional
from enum import Enum
from utils.base_data import BaseData
from .dto.meta_event_dto import (
    HeartbeatEventDTO,
    LifecycleEventDTO,
    HeartbeatStatusDto,
)


class LifecycleSubType(str, Enum):
    """生命周期子类型枚举"""
    ENABLE = "enable"  # 启用
    DISABLE = "disable"  # 禁用
    CONNECT = "connect"  # 连接


@dataclass(frozen=True)
class HeartbeatStatusData(BaseData):
    """心跳状态数据类"""
    online: Optional[bool]  # 是否在线
    good: bool  # 状态是否良好

    @classmethod
    def from_dto(cls, status: HeartbeatStatusDto) -> "HeartbeatStatusData":
        """从HeartbeatStatusDto构造HeartbeatStatusData实例"""
        return cls(
            online=status.online,
            good=status.good
        )


@dataclass(frozen=True)
class MetaEventBaseData(BaseData):
    """元事件基类数据类"""
    time: int  # 事件发生时间戳
    post_type: str  # 事件类型: meta_event
    self_id: int  # 收到事件的机器人QQ号
    meta_event_type: str  # 元事件类型: heartbeat/lifecycle


@dataclass(frozen=True)
class HeartbeatEventData(MetaEventBaseData):
    """心跳事件数据类"""
    status: HeartbeatStatusData  # 状态信息
    interval: int  # 心跳间隔时间(ms)

    @classmethod
    def from_dto(cls, dto: HeartbeatEventDTO) -> "HeartbeatEventData":
        """从HeartbeatEventDTO构造HeartbeatEventData实例

        Args:
            dto: HeartbeatEventDTO对象

        Returns:
            HeartbeatEventData实例
        """
        status_data = HeartbeatStatusData.from_dto(dto.status)

        return cls(
            time=dto.time,
            post_type=dto.post_type,
            self_id=dto.self_id,
            meta_event_type=dto.meta_event_type,
            status=status_data,
            interval=dto.interval
        )

    @property
    def is_online(self) -> bool:
        """机器人是否在线"""
        return self.status.online is True

    @property
    def is_good(self) -> bool:
        """状态是否良好"""
        return self.status.good


@dataclass(frozen=True)
class LifecycleEventData(MetaEventBaseData):
    """生命周期事件数据类"""
    sub_type: str  # 子类型: enable/disable/connect

    @classmethod
    def from_dto(cls, dto: LifecycleEventDTO) -> "LifecycleEventData":
        """从LifecycleEventDTO构造LifecycleEventData实例

        Args:
            dto: LifecycleEventDTO对象

        Returns:
            LifecycleEventData实例
        """
        return cls(
            time=dto.time,
            post_type=dto.post_type,
            self_id=dto.self_id,
            meta_event_type=dto.meta_event_type,
            sub_type=dto.sub_type
        )

    @property
    def lifecycle_type(self) -> Optional[LifecycleSubType]:
        """获取生命周期子类型枚举"""
        try:
            return LifecycleSubType(self.sub_type)
        except ValueError:
            return None

    @property
    def is_enable(self) -> bool:
        """是否为启用事件"""
        return self.sub_type == LifecycleSubType.ENABLE.value

    @property
    def is_disable(self) -> bool:
        """是否为禁用事件"""
        return self.sub_type == LifecycleSubType.DISABLE.value

    @property
    def is_connect(self) -> bool:
        """是否为连接事件"""
        return self.sub_type == LifecycleSubType.CONNECT.value

