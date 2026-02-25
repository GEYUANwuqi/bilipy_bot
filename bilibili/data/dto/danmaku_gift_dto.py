from logging import getLogger
from typing import Optional, ClassVar
from base_cls import BaseDataModel

_log = getLogger("DanmakuGiftDTO")


class BlindGiftInfoDto(BaseDataModel):
    """
    盲盒礼物信息（从盲盒中开出的礼物）
    """
    blind_gift_config_id: int  # 盲盒配置ID
    original_gift_id: int  # 原始盲盒礼物ID
    original_gift_name: str  # 原始盲盒礼物名称
    original_gift_price: int  # 原始盲盒价格（电池）
    gift_action: str  # 礼物动作描述（如"爆出"）
    gift_tip_price: int  # 开出礼物的价值（电池）


class GiftMedalInfoDto(BaseDataModel):
    """
    送礼用户的粉丝牌信息
    """
    level: int  # 勋章等级
    name: str  # 勋章名称
    anchor_room_id: int  # 主播房间号
    anchor_uname: str  # 主播名称（可能为空）
    guard_level: int  # 舰长等级 (0=无, 1=总督, 2=提督, 3=舰长)
    is_lighted: int  # 是否点亮 (1=点亮, 0=未点亮)
    target_id: int  # 勋章对应主播UID


class GiftInfoDto(BaseDataModel):
    """
    礼物资源信息
    """
    img_basic: str  # 礼物基础图片URL
    gif: str  # 礼物动图URL
    webp: str  # 礼物webp图片URL


class GiftSenderDto(BaseDataModel):
    """
    送礼用户信息
    """
    uid: int  # 用户UID
    uname: str  # 用户名
    face: str  # 头像URL
    guard_level: int  # 舰长等级 (0=无, 1=总督, 2=提督, 3=舰长)
    wealth_level: int  # 荣耀等级


class GiftReceiverDto(BaseDataModel):
    """
    收礼用户信息（主播）
    """
    uid: int  # 用户UID
    uname: str  # 用户名
    face: str  # 头像URL
    official_title: str  # 认证描述


class DanmakuGiftDTO(BaseDataModel):
    """
    礼物消息DTO
    """
    discriminator_value: ClassVar[str] = "danmaku_gift"  # 数据类型标识

    room_display_id: int  # 房间号
    room_real_id: int  # 房间真实ID
    gift_id: int  # 礼物ID
    gift_name: str  # 礼物名称
    gift_num: int  # 礼物数量
    price: int  # 单个礼物价格（电池）
    total_coin: int  # 总价值（电池）
    coin_type: str  # 货币类型 (gold=电池, silver=银瓜子)
    action: str  # 动作描述（如"投喂"）
    sender: GiftSenderDto  # 送礼用户信息
    receiver: GiftReceiverDto  # 收礼用户信息（主播）
    medal: Optional[GiftMedalInfoDto] = None  # 粉丝牌信息
    gift_info: Optional[GiftInfoDto] = None  # 礼物资源信息
    blind_gift: Optional[BlindGiftInfoDto] = None  # 盲盒礼物信息
    timestamp: int = 0  # 发送时间戳
    is_first: bool = False  # 是否首次送礼 (单次送礼, 无连击)
    combo_total_coin: int = 0  # 连击总价值

    @classmethod
    def from_raw(cls, data: dict) -> "Optional[DanmakuGiftDTO]":
        """
        从原始API数据构造DTO对象
        """
        try:
            room_display_id = data.get("room_display_id", 0)
            room_real_id = data.get("room_real_id", 0)

            # 获取内层data
            gift_data = data.get("data", {}).get("data", {})

            # 送礼用户信息
            sender = {
                "uid": gift_data.get("uid", 0),
                "uname": gift_data.get("uname", ""),
                "face": gift_data.get("face", ""),
                "guard_level": gift_data.get("guard_level", 0),
                "wealth_level": gift_data.get("wealth_level", 0)
            }

            # 收礼用户信息（主播）
            receiver_uinfo = gift_data.get("receiver_uinfo", {})
            receiver_base = receiver_uinfo.get("base", {})
            receiver = {
                "uid": receiver_uinfo.get("uid", 0),
                "uname": receiver_base.get("name", ""),
                "face": receiver_base.get("face", ""),
                "official_title": receiver_base.get("official_info", {}).get("title", "")
            }

            # 粉丝牌信息
            medal = None
            medal_info = gift_data.get("medal_info", {})
            if medal_info:
                medal = {
                    "level": medal_info.get("medal_level", 0),
                    "name": medal_info.get("medal_name", ""),
                    "anchor_room_id": medal_info.get("anchor_roomid", 0),
                    "anchor_uname": medal_info.get("anchor_uname", ""),
                    "guard_level": medal_info.get("guard_level", 0),
                    "is_lighted": medal_info.get("is_lighted", 0),
                    "target_id": medal_info.get("target_id", 0)
                }

            # 礼物资源信息
            gift_info = None
            gift_info_data = gift_data.get("gift_info", {})
            if gift_info_data:
                gift_info = {
                    "img_basic": gift_info_data.get("img_basic", ""),
                    "gif": gift_info_data.get("gif", ""),
                    "webp": gift_info_data.get("webp", "")
                }

            # 盲盒礼物信息
            blind_gift = None
            blind_gift_data = gift_data.get("blind_gift")
            if blind_gift_data:
                blind_gift = {
                    "blind_gift_config_id": blind_gift_data.get("blind_gift_config_id", 0),
                    "original_gift_id": blind_gift_data.get("original_gift_id", 0),
                    "original_gift_name": blind_gift_data.get("original_gift_name", ""),
                    "original_gift_price": blind_gift_data.get("original_gift_price", 0),
                    "gift_action": blind_gift_data.get("gift_action", ""),
                    "gift_tip_price": blind_gift_data.get("gift_tip_price", 0)
                }

            # 构造标准化字典后使用model_validate
            normalized_data = {
                "room_display_id": room_display_id,
                "room_real_id": room_real_id,
                "gift_id": gift_data.get("giftId", 0),
                "gift_name": gift_data.get("giftName", ""),
                "gift_num": gift_data.get("num", 1),
                "price": gift_data.get("price", 0),
                "total_coin": gift_data.get("total_coin", 0),
                "coin_type": gift_data.get("coin_type", "gold"),
                "action": gift_data.get("action", ""),
                "sender": sender,
                "receiver": receiver,
                "medal": medal,
                "gift_info": gift_info,
                "blind_gift": blind_gift,
                "timestamp": gift_data.get("timestamp", 0),
                "is_first": gift_data.get("is_first", False),
                "combo_total_coin": gift_data.get("combo_total_coin", 0)
            }

            return cls.model_validate(normalized_data)

        except Exception as e:
            _log.error(f"解析礼物消息失败: {e}")
            return None
