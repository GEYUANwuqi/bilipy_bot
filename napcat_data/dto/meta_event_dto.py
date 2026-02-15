from utils.base_dto import BaseDto
from typing import Optional, Any
from logging import getLogger


_log = getLogger("MetaEventDTO")


class HeartbeatStatusDto(BaseDto):
    """心跳状态数据传输对象"""
    online: Optional[bool] = None  # 是否在线
    good: bool = False  # 状态是否良好

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Optional[HeartbeatStatusDto]":
        """从字典构造心跳状态对象"""
        try:
            return cls(
                online=data.get("online"),
                good=data.get("good", False)
            )
        except Exception as e:
            _log.error(f"解析心跳状态失败: {e}", exc_info=True)
            return None


class MetaEventBaseDTO(BaseDto):
    """元事件基类数据传输对象"""
    time: int  # 事件发生时间戳
    post_type: str  # 事件类型: meta_event
    self_id: int  # 收到事件的机器人QQ号
    meta_event_type: str  # 元事件类型: heartbeat/lifecycle


class HeartbeatEventDTO(MetaEventBaseDTO):
    """心跳事件数据传输对象"""
    status: HeartbeatStatusDto  # 状态信息
    interval: int  # 心跳间隔时间(ms)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Optional[HeartbeatEventDTO]":
        """
        从字典构造心跳事件DTO对象

        Args:
            data: 心跳事件数据字典

        Returns:
            HeartbeatEventDTO对象，解析失败返回None
        """
        try:
            # 解析状态信息
            status_data = data.get("status", {})
            status_dto = HeartbeatStatusDto.from_dict(status_data)
            if not status_dto:
                status_dto = HeartbeatStatusDto(online=None, good=False)

            return cls(
                time=data.get("time", 0),
                post_type=data.get("post_type", ""),
                self_id=data.get("self_id", 0),
                meta_event_type=data.get("meta_event_type", ""),
                status=status_dto,
                interval=data.get("interval", 0)
            )
        except Exception as e:
            _log.error(f"解析心跳事件数据失败: {e}", exc_info=True)
            return None


class LifecycleEventDTO(MetaEventBaseDTO):
    """生命周期事件数据传输对象"""
    sub_type: str  # 子类型: enable/disable/connect

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Optional[LifecycleEventDTO]":
        """
        从字典构造生命周期事件DTO对象

        Args:
            data: 生命周期事件数据字典

        Returns:
            LifecycleEventDTO对象，解析失败返回None
        """
        try:
            return cls(
                time=data.get("time", 0),
                post_type=data.get("post_type", ""),
                self_id=data.get("self_id", 0),
                meta_event_type=data.get("meta_event_type", ""),
                sub_type=data.get("sub_type", "")
            )
        except Exception as e:
            _log.error(f"解析生命周期事件数据失败: {e}", exc_info=True)
            return None

