from dataclasses import dataclass
from typing import Optional, Any, List
from utils.base_data import BaseData
from .dto.message_base_dto import MessageSegmentDto, SenderDto


@dataclass(frozen=True)
class MessageSegmentData(BaseData):
    """消息段数据类"""
    type: str  # 消息段类型，如: text, at, face, image等
    data: dict[str, Any]  # 消息段数据

    @classmethod
    def from_dto(cls, segment: MessageSegmentDto) -> "MessageSegmentData":
        """从MessageSegmentDto构造MessageSegmentData实例"""
        return cls(
            type=segment.type,
            data=segment.data
        )

    @property
    def text_content(self) -> Optional[str]:
        """获取文本内容（如果是text类型）"""
        if self.type == "text":
            return self.data.get("text")
        return None

    @property
    def at_qq(self) -> Optional[int]:
        """获取@的QQ号（如果是at类型）"""
        if self.type == "at":
            qq = self.data.get("qq")
            return int(qq) if qq else None
        return None


@dataclass(frozen=True)
class SenderData(BaseData):
    """发送者信息数据类（基类）"""
    user_id: int  # 发送者QQ号
    nickname: str  # 发送者昵称
    sex: Optional[str]  # 性别: male/female/unknown

    @classmethod
    def from_dto(cls, sender: SenderDto) -> "SenderData":
        """从SenderDto构造SenderData实例"""
        return cls(
            user_id=sender.user_id,
            nickname=sender.nickname,
            sex=sender.sex
        )


@dataclass(frozen=True)
class MessageBaseData(BaseData):
    """消息基类数据类"""
    time: int  # 消息发送时间戳
    post_type: str  # 上报类型: message
    message_type: str  # 消息类型: group/private
    sub_type: str  # 消息子类型
    message_id: int  # 消息ID
    user_id: int  # 发送者QQ号
    message: List[MessageSegmentData]  # 消息段列表
    raw_message: str  # 原始消息内容（CQ码格式）
    font: int  # 字体
    self_id: int  # 机器人自身QQ号

    @property
    def plain_text(self) -> str:
        """获取纯文本消息内容（仅包含text类型的消息段）"""
        text_parts = []
        for segment in self.message:
            if segment.type == "text":
                text = segment.data.get("text", "")
                text_parts.append(text)
        return "".join(text_parts)

    @property
    def at_list(self) -> List[int]:
        """获取消息中@的所有QQ号列表"""
        at_list = []
        for segment in self.message:
            if segment.type == "at":
                qq = segment.data.get("qq")
                if qq:
                    try:
                        at_list.append(int(qq))
                    except (ValueError, TypeError):
                        pass
        return at_list

    @property
    def is_at_bot(self) -> bool:
        """消息是否@了机器人"""
        return self.self_id in self.at_list
