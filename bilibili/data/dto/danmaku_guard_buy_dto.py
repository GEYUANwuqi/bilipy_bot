from logging import getLogger
from typing import Optional, ClassVar
from base_cls import BaseDataModel

_log = getLogger("DanmakuGuardDTO")


class DanmakuGuardDTO(BaseDataModel):
    """
    舰长事件 DTO
    guard_level: 舰长等级 (1=总督, 2=提督, 3=舰长)
    """
    discriminator_value: ClassVar[str] = "guard"  # 数据类型标识

    room_display_id: int  # 房间号
    room_real_id: int  # 房间真实ID
    uid: int  # 用户UID
    username: str  # 用户名
    guard_level: int  # 舰长等级 (1=总督, 2=提督, 3=舰长)
    num: int  # 购买数量
    price: int  # 价格（电池）
    gift_id: int  # 礼物ID
    gift_name: str  # 礼物名称（如"舰长"）

    @classmethod
    def from_raw(cls, data: dict) -> "Optional[DanmakuGuardDTO]":
        """
        从原始API数据构造DTO对象
        """
        try:
            room_display_id = data.get("room_display_id", 0)
            room_real_id = data.get("room_real_id", 0)

            guard_data = data.get("data", {}).get("data", {})

            normalized_data = {
                "room_display_id": room_display_id,
                "room_real_id": room_real_id,
                "uid": guard_data.get("uid", 0),
                "username": guard_data.get("username", ""),
                "guard_level": guard_data.get("guard_level", 3),
                "num": guard_data.get("num", 1),
                "price": guard_data.get("price", 0),
                "gift_id": guard_data.get("gift_id", 0),
                "gift_name": guard_data.get("gift_name", ""),
            }

            return cls.model_validate(normalized_data)

        except Exception as e:
            _log.error(f"解析上舰数据失败: {e}", exc_info=True)
            return None
