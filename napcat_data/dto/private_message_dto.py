from typing import Optional, Any
from logging import getLogger

from .message_base_dto import MessageBaseDTO, MessageSegmentDto, PrivateSenderDto


_log = getLogger("PrivateMessageDTO")


class PrivateMessageDTO(MessageBaseDTO):
    """私聊消息数据传输对象（DTO）"""
    sender: PrivateSenderDto  # 发送者信息

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Optional[PrivateMessageDTO]":
        """
        从字典构造私聊消息DTO对象

        Args:
            data: 私聊消息数据字典

        Returns:
            PrivateMessageDTO对象，解析失败返回None
        """
        try:
            # 解析消息段列表
            message_segments = []
            message_data = data.get("message", [])
            for segment in message_data:
                segment_dto = MessageSegmentDto.from_dict(segment)
                if segment_dto:
                    message_segments.append(segment_dto)

            # 解析发送者信息
            sender_data = data.get("sender", {})
            sender_dto = PrivateSenderDto.from_dict(sender_data)
            if not sender_dto:
                _log.warning("发送者信息解析失败，使用默认值")
                sender_dto = PrivateSenderDto(
                    user_id=data.get("user_id", 0),
                    nickname="",
                )

            return cls(
                time=data.get("time", 0),
                post_type=data.get("post_type", ""),
                message_type=data.get("message_type", ""),
                sub_type=data.get("sub_type", ""),
                message_id=data.get("message_id", 0),
                user_id=data.get("user_id", 0),
                message=message_segments,
                raw_message=data.get("raw_message", ""),
                font=data.get("font", 0),
                sender=sender_dto,
                self_id=data.get("self_id", 0)
            )

        except Exception as e:
            _log.error(f"解析私聊消息数据失败: {e}", exc_info=True)
            return None
