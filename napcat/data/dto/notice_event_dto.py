from base_cls import BaseDto
from typing import Optional, Any
from logging import getLogger


_log = getLogger("NoticeEventDTO")


class NoticeEventDTO(BaseDto):
    """通知事件数据传输对象（DTO）"""
    time: int  # 事件发生时间戳
    post_type: str  # 事件类型: notice
    self_id: int  # 收到事件的机器人QQ号
    notice_type: str  # 通知类型

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Optional[NoticeEventDTO]":
        """
        从字典构造通知事件DTO对象

        Args:
            data: 通知事件数据字典

        Returns:
            NoticeEventDTO对象，解析失败返回None
        """
        try:
            return cls(
                time=data.get("time", 0),
                post_type=data.get("post_type", ""),
                self_id=data.get("self_id", 0),
                notice_type=data.get("notice_type", "")
            )
        except Exception as e:
            _log.error(f"解析通知事件数据失败: {e}", exc_info=True)
            return None

