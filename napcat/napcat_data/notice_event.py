from dataclasses import dataclass
from base_cls import BaseData
from .dto import NoticeEventDTO


@dataclass(frozen=True)
class NoticeEventData(BaseData):
    """通知事件数据类"""
    time: int  # 事件发生时间戳
    post_type: str  # 事件类型: notice
    self_id: int  # 收到事件的机器人QQ号
    notice_type: str  # 通知类型

    @classmethod
    def from_dto(cls, dto: NoticeEventDTO) -> "NoticeEventData":
        """从NoticeEventDTO构造NoticeEventData实例

        Args:
            dto: NoticeEventDTO对象

        Returns:
            NoticeEventData实例
        """
        return cls(
            time=dto.time,
            post_type=dto.post_type,
            self_id=dto.self_id,
            notice_type=dto.notice_type
        )

