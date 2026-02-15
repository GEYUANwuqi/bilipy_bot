from dataclasses import dataclass
from typing import Optional
from .message_base import MessageBaseData, MessageSegmentData, SenderData
from .dto.group_message_dto import GroupMessageDTO, GroupSenderDto


@dataclass(frozen=True)
class GroupSenderData(SenderData):
    """群消息发送者信息数据类"""
    card: Optional[str] = None  # 群名片
    role: Optional[str] = None  # 角色: owner/admin/member

    @classmethod
    def from_dto(cls, sender: GroupSenderDto) -> "GroupSenderData":
        """从GroupSenderDto构造GroupSenderData实例"""
        return cls(
            user_id=sender.user_id,
            nickname=sender.nickname,
            sex=sender.sex,
            card=sender.card,
            role=sender.role
        )

    @property
    def display_name(self) -> str:
        """获取显示名称（优先使用群名片，否则使用昵称）"""
        return self.card if self.card else self.nickname

    @property
    def is_admin(self) -> bool:
        """是否为管理员（包括群主）"""
        return self.role in ("owner", "admin")

    @property
    def is_owner(self) -> bool:
        """是否为群主"""
        return self.role == "owner"


@dataclass(frozen=True)
class GroupMessageData(MessageBaseData):
    """群消息数据类"""
    group_id: int  # 群号
    sender: GroupSenderData  # 发送者信息

    @classmethod
    def from_dto(cls, dto: GroupMessageDTO) -> "GroupMessageData":
        """从GroupMessageDTO构造GroupMessageData实例

        Args:
            dto: GroupMessageDTO对象

        Returns:
            GroupMessageData实例
        """
        # 消息段列表
        message_segments = [
            MessageSegmentData.from_dto(segment)
            for segment in dto.message
        ]

        # 发送者信息
        sender_data = GroupSenderData.from_dto(dto.sender)

        return cls(
            time=dto.time,
            post_type=dto.post_type,
            message_type=dto.message_type,
            sub_type=dto.sub_type,
            message_id=dto.message_id,
            user_id=dto.user_id,
            group_id=dto.group_id,
            message=message_segments,
            raw_message=dto.raw_message,
            font=dto.font,
            sender=sender_data,
            self_id=dto.self_id
        )
