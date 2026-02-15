from dataclasses import dataclass
from typing import Optional
from .message_base import MessageBaseData, MessageSegmentData, SenderData
from .dto.private_message_dto import PrivateMessageDTO, PrivateSenderDto


@dataclass(frozen=True)
class PrivateSenderData(SenderData):
    """私聊消息发送者信息数据类"""
    age: Optional[int] = None  # 年龄

    @classmethod
    def from_dto(cls, sender: PrivateSenderDto) -> "PrivateSenderData":
        """从PrivateSenderDto构造PrivateSenderData实例"""
        return cls(
            user_id=sender.user_id,
            nickname=sender.nickname,
            sex=sender.sex,
            age=sender.age
        )


@dataclass(frozen=True)
class PrivateMessageData(MessageBaseData):
    """私聊消息数据类"""
    sender: PrivateSenderData  # 发送者信息

    @classmethod
    def from_dto(cls, dto: PrivateMessageDTO) -> "PrivateMessageData":
        """从PrivateMessageDTO构造PrivateMessageData实例

        Args:
            dto: PrivateMessageDTO对象

        Returns:
            PrivateMessageData实例
        """
        # 消息段列表
        message_segments = [
            MessageSegmentData.from_dto(segment)
            for segment in dto.message
        ]

        # 发送者信息
        sender_data = PrivateSenderData.from_dto(dto.sender)

        return cls(
            time=dto.time,
            post_type=dto.post_type,
            message_type=dto.message_type,
            sub_type=dto.sub_type,
            message_id=dto.message_id,
            user_id=dto.user_id,
            message=message_segments,
            raw_message=dto.raw_message,
            font=dto.font,
            sender=sender_data,
            self_id=dto.self_id
        )
