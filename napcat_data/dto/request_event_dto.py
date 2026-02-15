from utils.base_dto import BaseDto
from typing import Optional, Any
from logging import getLogger


_log = getLogger("RequestEventDTO")


class RequestEventDTO(BaseDto):
    """请求事件数据传输对象（DTO）"""
    time: int  # 事件发生时间戳
    post_type: str  # 事件类型: request
    self_id: int  # 收到事件的机器人QQ号
    request_type: str  # 请求类型: friend/group
    flag: str  # 请求flag
    user_id: int  # 发送请求的QQ号
    comment: str  # 验证信息

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Optional[RequestEventDTO]":
        """
        从字典构造请求事件DTO对象

        Args:
            data: 请求事件数据字典

        Returns:
            RequestEventDTO对象，解析失败返回None
        """
        try:
            return cls(
                time=data.get("time", 0),
                post_type=data.get("post_type", ""),
                self_id=data.get("self_id", 0),
                request_type=data.get("request_type", ""),
                flag=data.get("flag", ""),
                user_id=data.get("user_id", 0),
                comment=data.get("comment", "")
            )
        except Exception as e:
            _log.error(f"解析请求事件数据失败: {e}", exc_info=True)
            return None

