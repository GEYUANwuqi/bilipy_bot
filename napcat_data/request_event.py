from dataclasses import dataclass
from utils.base_data import BaseData
from .dto.request_event_dto import RequestEventDTO


@dataclass(frozen=True)
class RequestEventData(BaseData):
    """请求事件数据类"""
    time: int  # 事件发生时间戳
    post_type: str  # 事件类型: request
    self_id: int  # 收到事件的机器人QQ号
    request_type: str  # 请求类型: friend/group
    flag: str  # 请求flag
    user_id: int  # 发送请求的QQ号
    comment: str  # 验证信息

    @classmethod
    def from_dto(cls, dto: RequestEventDTO) -> "RequestEventData":
        """从RequestEventDTO构造RequestEventData实例

        Args:
            dto: RequestEventDTO对象

        Returns:
            RequestEventData实例
        """
        return cls(
            time=dto.time,
            post_type=dto.post_type,
            self_id=dto.self_id,
            request_type=dto.request_type,
            flag=dto.flag,
            user_id=dto.user_id,
            comment=dto.comment
        )

    @property
    def is_friend_request(self) -> bool:
        """是否为好友请求"""
        return self.request_type == "friend"

    @property
    def is_group_request(self) -> bool:
        """是否为群请求"""
        return self.request_type == "group"

