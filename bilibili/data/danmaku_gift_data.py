from typing import Optional
from dataclasses import dataclass

from base_cls import BaseDataMixin
from .dto import DanmakuGiftDTO, GiftMedalInfoDto, BlindGiftInfoDto


@dataclass(frozen=True)
class GiftMedalData(BaseDataMixin):
    """
    送礼用户粉丝牌数据
    """
    level: int  # 粉丝牌等级
    name: str  # 粉丝牌名称
    anchor_room_id: int  # 粉丝牌对应主播房间号
    anchor_uname: str  # 粉丝牌对应主播名称
    guard_level: int  # 舰长等级 (0=无, 1=总督, 2=提督, 3=舰长)
    is_lighted: int  # 粉丝牌是否点亮 (1=点亮, 0=未点亮)
    anchor_uid: int  # 粉丝牌对应主播UID

    @classmethod
    def from_dto(cls, medal: GiftMedalInfoDto) -> "GiftMedalData":
        """从GiftMedalInfoDto构造GiftMedalData实例"""
        return cls(
            level=medal.level,
            name=medal.name,
            anchor_room_id=medal.anchor_room_id,
            anchor_uname=medal.anchor_uname,
            guard_level=medal.guard_level,
            is_lighted=medal.is_lighted,
            anchor_uid=medal.target_id
        )


@dataclass(frozen=True)
class BlindGiftData(BaseDataMixin):
    """
    盲盒礼物数据（从盲盒中开出的礼物信息）
    """
    blind_gift_config_id: int  # 盲盒配置ID
    original_gift_id: int  # 原始盲盒礼物ID
    original_gift_name: str  # 原始盲盒礼物名称
    original_gift_price: int  # 原始盲盒价格（电池）
    gift_action: str  # 礼物动作描述（如"爆出"）
    gift_tip_price: int  # 开出礼物的价值（电池）

    @classmethod
    def from_dto(cls, blind_gift: BlindGiftInfoDto) -> "BlindGiftData":
        """从BlindGiftInfoDto构造BlindGiftData实例"""
        return cls(
            blind_gift_config_id=blind_gift.blind_gift_config_id,
            original_gift_id=blind_gift.original_gift_id,
            original_gift_name=blind_gift.original_gift_name,
            original_gift_price=blind_gift.original_gift_price,
            gift_action=blind_gift.gift_action,
            gift_tip_price=blind_gift.gift_tip_price
        )


@dataclass(frozen=True)
class DanmakuGiftData(BaseDataMixin):
    """
    礼物消息数据
    """
    room_display_id: int  # 房间号
    room_real_id: int  # 房间真实ID
    gift_id: int  # 礼物ID
    gift_name: str  # 礼物名称
    gift_num: int  # 礼物数量
    price: int  # 单个礼物价格（电池）
    total_coin: int  # 总价值（电池）
    coin_type: str  # 货币类型 (gold=电池)
    action: str  # 动作描述（如"投喂"）
    uid: int  # 送礼用户UID
    uname: str  # 送礼用户名
    face: str  # 送礼用户头像URL
    guard_level: int  # 舰长等级 (0=无, 1=总督, 2=提督, 3=舰长)
    wealth_level: int  # 荣耀等级
    receiver_uid: int  # 收礼用户UID（主播）
    receiver_uname: str  # 收礼用户名（主播）
    receiver_face: str  # 收礼用户头像URL（主播）
    receiver_official_title: str  # 认证描述
    medal: Optional[GiftMedalData]  # 粉丝牌信息
    blind_gift: Optional[BlindGiftData]  # 盲盒礼物信息
    timestamp: int  # 发送时间戳
    is_first: bool  # 是否首次送礼
    combo_total_coin: int  # 连击总价值
    gift_gif: str  # 礼物动图URL
    gift_img: str  # 礼物图片URL

    @classmethod
    def from_dto(cls, dto: DanmakuGiftDTO) -> "DanmakuGiftData":
        """从DTO对象构造DanmakuGiftData实例

        Args:
            dto: DanmakuGiftDTO对象

        Returns:
            DanmakuGiftData实例
        """
        medal_data = GiftMedalData.from_dto(dto.medal) if dto.medal else None
        blind_gift_data = BlindGiftData.from_dto(dto.blind_gift) if dto.blind_gift else None

        return cls(
            room_display_id=dto.room_display_id,
            room_real_id=dto.room_real_id,
            gift_id=dto.gift_id,
            gift_name=dto.gift_name,
            gift_num=dto.gift_num,
            price=dto.price,
            total_coin=dto.total_coin,
            coin_type=dto.coin_type,
            action=dto.action,
            uid=dto.sender.uid,
            uname=dto.sender.uname,
            face=dto.sender.face,
            guard_level=dto.sender.guard_level,
            wealth_level=dto.sender.wealth_level,
            receiver_uid=dto.receiver.uid,
            receiver_uname=dto.receiver.uname,
            receiver_face=dto.receiver.face,
            receiver_official_title=dto.receiver.official_title,
            medal=medal_data,
            blind_gift=blind_gift_data,
            timestamp=dto.timestamp,
            is_first=dto.is_first,
            combo_total_coin=dto.combo_total_coin,
            gift_gif=dto.gift_info.gif,
            gift_img=dto.gift_info.img_basic
        )
