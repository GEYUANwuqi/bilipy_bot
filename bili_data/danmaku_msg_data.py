from typing import Optional
from dataclasses import dataclass

from .base_data import BaseData
from .dto import DanmakuMsgDTO, MedalInfoDto


@dataclass(frozen=True)
class MedalData(BaseData):
    """
    粉丝牌数据
    """
    level: int  # 粉丝牌等级
    name: str  # 粉丝牌名称
    anchor_name: str  # 粉丝牌对应主播名
    room_id: int  # 粉丝牌对应主播房间号
    is_light: int  # 粉丝牌是否点亮 (1=点亮, 0=未点亮)
    anchor_uid: int  # 粉丝牌对应主播UID

    @classmethod
    def from_dto(cls, medal: MedalInfoDto) -> "MedalData":
        """从MedalInfo DTO构造MedalData实例"""
        return cls(
            level=medal.level,
            name=medal.name,
            anchor_name=medal.anchor_name,
            room_id=medal.room_id,
            is_light=medal.is_light,
            anchor_uid=medal.anchor_uid
        )


@dataclass(frozen=True)
class DanmakuMsgData(BaseData):
    """
    弹幕消息数据
    """
    room_display_id: int  # 房间短号
    room_real_id: int  # 房间真实ID
    message: str  # 弹幕内容
    uid: int  # 用户UID
    username: str  # 用户名
    user_level: int  # 用户等级
    face: Optional[str]  # 头像URL
    medal: Optional[MedalData]  # 粉丝牌信息
    timestamp: int  # 发送时间戳

    @classmethod
    def from_dto(cls, dto: DanmakuMsgDTO) -> "DanmakuMsgData":
        """从DTO对象构造DanmakuMsgData实例

        Args:
            dto: DanmakuMsgDTO对象

        Returns:
            DanmakuMsgData实例
        """
        medal_data = MedalData.from_dto(dto.medal) if dto.medal else None
        return cls(
            room_display_id=dto.room_display_id,
            room_real_id=dto.room_real_id,
            message=dto.message,
            uid=dto.user.uid,
            username=dto.user.username,
            user_level=dto.user.user_level,
            face=dto.user.face,
            medal=medal_data,
            timestamp=dto.timestamp
        )
