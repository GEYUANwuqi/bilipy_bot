from dataclasses import dataclass

from base_cls import BaseDataMixin
from .dto import DanmakuGuardDTO

# 舰长等级名称映射
GUARD_LEVEL_NAME = {
    1: "总督",
    2: "提督",
    3: "舰长",
}


@dataclass(frozen=True)
class DanmakuGuardData(BaseDataMixin):
    """
    上舰事件数据
    guard_level: 舰长等级 (1=总督, 2=提督, 3=舰长)
    """
    room_display_id: int  # 房间号
    room_real_id: int  # 房间真实ID
    uid: int  # 用户UID
    username: str  # 用户名
    guard_level: int  # 舰长等级 (1=总督, 2=提督, 3=舰长)
    guard_name: str  # 舰长等级名称（如"舰长"）
    num: int  # 购买数量
    price: int  # 价格（电池）
    gift_id: int  # 礼物ID
    gift_name: str  # 礼物名称（如"舰长"）

    @classmethod
    def from_dto(cls, dto: DanmakuGuardDTO) -> "DanmakuGuardData":
        """从DTO对象构造DanmakuGuardData实例

        Args:
            dto: DanmakuGuardDTO对象

        Returns:
            DanmakuGuardData实例
        """
        return cls(
            room_display_id=dto.room_display_id,
            room_real_id=dto.room_real_id,
            uid=dto.uid,
            username=dto.username,
            guard_level=dto.guard_level,
            guard_name=GUARD_LEVEL_NAME.get(dto.guard_level, "未知类型"),
            num=dto.num,
            price=dto.price,
            gift_id=dto.gift_id,
            gift_name=dto.gift_name,
        )
