from base_cls import BaseDto
from typing import Optional, Any, List
from logging import getLogger


_log = getLogger("MessageBaseDTO")


class MessageSegmentDto(BaseDto):
    """消息段数据传输对象"""
    type: str  # 消息段类型，如: text, at, face, image等
    data: dict[str, Any]  # 消息段数据

    @classmethod
    def from_dict(cls, segment_data: dict[str, Any]) -> "Optional[MessageSegmentDto]":
        """
        从字典构造消息段对象
        """
        try:
            return cls(
                type=segment_data.get("type", ""),
                data=segment_data.get("data", {})
            )
        except Exception as e:
            _log.error(f"解析消息段失败: {e}", exc_info=True)
            return None


class SenderDto(BaseDto):
    """发送者信息数据传输对象（基类）"""
    user_id: int  # 发送者QQ号
    nickname: str  # 发送者昵称
    sex: Optional[str] = None  # 性别: male/female/unknown

    @classmethod
    def from_dict(cls, sender_data: dict[str, Any]) -> "Optional[SenderDto]":
        """
        从字典构造发送者信息对象
        """
        try:
            return cls(
                user_id=sender_data.get("user_id", 0),
                nickname=sender_data.get("nickname", ""),
                sex=sender_data.get("sex")
            )
        except Exception as e:
            _log.error(f"解析发送者信息失败: {e}", exc_info=True)
            return None


class GroupSenderDto(SenderDto):
    """群消息发送者信息数据传输对象"""
    card: Optional[str] = None  # 群名片
    role: Optional[str] = None  # 角色: owner/admin/member

    @classmethod
    def from_dict(cls, sender_data: dict[str, Any]) -> "Optional[GroupSenderDto]":
        """
        从字典构造群发送者信息对象
        """
        try:
            return cls(
                user_id=sender_data.get("user_id", 0),
                nickname=sender_data.get("nickname", ""),
                sex=sender_data.get("sex"),
                card=sender_data.get("card"),
                role=sender_data.get("role")
            )
        except Exception as e:
            _log.error(f"解析群发送者信息失败: {e}", exc_info=True)
            return None


class PrivateSenderDto(SenderDto):
    """私聊消息发送者信息数据传输对象"""
    age: Optional[int] = None  # 年龄

    @classmethod
    def from_dict(cls, sender_data: dict[str, Any]) -> "Optional[PrivateSenderDto]":
        """
        从字典构造私聊发送者信息对象
        """
        try:
            return cls(
                user_id=sender_data.get("user_id", 0),
                nickname=sender_data.get("nickname", ""),
                sex=sender_data.get("sex"),
                age=sender_data.get("age")
            )
        except Exception as e:
            _log.error(f"解析私聊发送者信息失败: {e}", exc_info=True)
            return None


class MessageBaseDTO(BaseDto):
    """消息基类数据传输对象（DTO）"""
    time: int  # 消息发送时间戳
    post_type: str  # 上报类型: message
    message_type: str  # 消息类型: group/private
    sub_type: str  # 消息子类型
    message_id: int  # 消息ID
    user_id: int  # 发送者QQ号
    message: List[MessageSegmentDto]  # 消息段列表
    raw_message: str  # 原始消息内容（CQ码格式）
    font: int  # 字体
    self_id: int  # 机器人自身QQ号
