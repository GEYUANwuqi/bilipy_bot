from bilibili_api import Credential
from bilibili_api.user import User
from bilibili_api.live import LiveRoom
from bili_data import DynamicData, LiveRoomData, get_max_id, DynamicDTO
from .base_api import BaseApi
from .context import APIContext
from logging import getLogger
from typing import Optional

_log = getLogger("BilibiliApi")


class BilibiliApi(BaseApi):

    def __init__(self, credential: Optional[Credential]) -> None:
        """初始化BilibiliApi客户端
        Args:
            credential: Optional[Credential]: B站用户凭证
        """
        self.credential = credential

    @classmethod
    def create(cls, ctx: APIContext) -> "BilibiliApi":
        return cls(
            ctx.config.get_config("bilibili")
        )

    async def get_all_dynamic(self, uid: int) -> list[DynamicData]:
        """
        获取单页动态(谨慎使用)
        Args:
            uid (int): 用户uid
        Returns:
            list[DynamicData]: 动态信息对象
        """

        user = User(credential = self.credential, uid = uid)
        dict_info = await user.get_dynamics_new()
        info_dto = [DynamicDTO.from_dict(item) for item in dict_info["items"]]
        info = [DynamicData.from_dto(dto) for dto in info_dto if dto is not None]
        return info

    async def get_new_dynamic(self, uid: int) -> DynamicData:
        """
        获取最新的一条动态
        Args:
            uid (int): 用户uid
        Returns:
            DynamicData: 动态信息对象
        """

        user = User(credential = self.credential, uid = uid)
        dict_info = await user.get_dynamics_new()
        max_id = get_max_id(dict_info)
        _log.debug(f"获取到最大时间戳的索引为'{max_id}'")
        dynamic_info = dict_info["items"][max_id]
        dto = DynamicDTO.from_dict(dynamic_info)
        if not dto:
            raise ValueError(f"Failed to parse dynamic data for uid {uid}")
        info = DynamicData.from_dto(dto)
        return info

    async def get_room_info(self, room_id: int) -> LiveRoomData:
        """
        获取直播间信息
        Args:
            room_id (int): 直播间ID
        Returns:
            LiveRoomData: 直播间信息对象
        """

        live_room = LiveRoom(credential = self.credential, room_display_id = room_id)
        live = await live_room.get_room_info()
        info = LiveRoomData(live)
        return info
