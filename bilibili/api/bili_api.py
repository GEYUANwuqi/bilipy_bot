from bilibili_api import Credential
from bilibili_api.user import User
from bilibili_api.live import LiveRoom
from bilibili_api.dynamic import get_dynamic_page_info

from bilibili.data import DynamicData, LiveRoomData, get_max_id
from bilibili.data.dto import DynamicDTO, LiveRoomDTO
from base_cls import BaseApi

from logging import getLogger
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from manager.context import APIContext

_log = getLogger("BilibiliApi")


class BilibiliApi(BaseApi):

    def __init__(self, credential: Optional[Credential]) -> None:
        """初始化BilibiliApi客户端
        Args:
            credential: Optional[Credential]: B站用户凭证
        """
        self.credential = credential

    @classmethod
    def create(cls, ctx: "APIContext") -> "BilibiliApi":
        return cls(
            ctx.config.get_config("bilibili")
        )

    async def get_all_dynamic(self, uid: int, offset: str = "") -> list[DynamicData]:
        """
        获取单页动态
        Args:
            uid (int): 用户uid
            offset (str): 分页偏移参数
        Returns:
            list[DynamicData]: 动态信息对象
        """

        user = User(credential = self.credential, uid = uid)
        dict_info = await user.get_dynamics_new(offset = offset)
        if dict_info.get("items", None) is None or not dict_info.get("items"):
            raise ValueError("未获取到动态数据或者动态数据为不完整")
        info_dto = DynamicDTO.from_list(dict_info["items"])
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
        if max_id is None:
            raise ValueError("未获取到动态数据或者动态数据为不完整")
        dynamic_info = dict_info["items"][max_id]
        dto = DynamicDTO.from_dict(dynamic_info)
        if not dto:
            raise ValueError(f"构造 {uid} 用户动态DTO对象失败")
        info = DynamicData.from_dto(dto)
        return info

    async def get_new_dynamic_list(self) -> list[DynamicData]:
        """获取动态主页的动态列表
        Returns:
            list[DynamicData]: 动态信息对象
        """
        dynamic_info = await get_dynamic_page_info(self.credential)
        if dynamic_info.get("items", None) is None or not dynamic_info.get("items"):
            raise ValueError("未获取到动态数据或者动态数据为不完整")
        info_dto = DynamicDTO.from_list(dynamic_info["items"])
        info = [DynamicData.from_dto(dto) for dto in info_dto if dto is not None]
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
        dto = LiveRoomDTO.from_dict(live)
        if dto is None:
            raise ValueError(f"构造直播间 {room_id} DTO对象失败")
        info = LiveRoomData.from_dto(dto)
        return info
