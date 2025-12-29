from bilibili_api import Credential
from bilibili_api.user import User
from bilibili_api.live import LiveRoom
from event import DynamicData, LiveData, get_max_id
from logging import getLogger

_log = getLogger("BilibiliApi")


class BilibiliApi:

    def __init__(self, sessdata: str = "") -> None:
        self.credential = Credential(sessdata = sessdata)

    async def get_all_dynamic(self, uid: int) -> list[DynamicData]:
        """
        获取所有动态(谨慎使用)
        Args:
            uid (int): 用户uid
        Returns:
            list[DynamicData]: 动态信息对象
        """

        user = User(credential = self.credential, uid = uid)
        dict_info = await user.get_dynamics_new()
        info = [DynamicData(item) for item in dict_info["items"]]
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
        info = DynamicData(dynamic_info)
        return info

    async def get_room_info(self, room_id: int) -> LiveData:
        """
        获取直播间信息
        Args:
            room_id (int): 直播间ID
        Returns:
            LiveData: 直播间信息对象
        """

        live_room = LiveRoom(credential = self.credential, room_display_id = room_id)
        live = await live_room.get_room_info()
        info = LiveData(live)
        return info
