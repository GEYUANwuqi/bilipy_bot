from typing import Any
from .base_data import BaseData


def get_max_id(date: dict) -> int:
    """获取最新动态的索引ID
    Args:
        date (dict): 动态数据
    Returns:
        max_id (int): 索引id

    """
    max_timestamp = 0
    max_id = 0
    list_data = date["items"]
    for index, item in enumerate(list_data):
        timestamp = item["modules"]["module_author"]["pub_ts"]
        if timestamp > max_timestamp:
            max_timestamp = timestamp
            max_id = index
    return max_id


class DynamicBaseData(BaseData):
    """动态基础数据类."""

    def __init__(self, data: dict[Any, Any]):
        """初始化DynamicBaseData对象.

        Args:
            data(dict): 单条动态信息
        """

        self.raw_data: dict[Any, Any] = data # 原始数据
        self.type: str = data["type"] # 动态类型
        self.id: str = data["id_str"] # 动态ID
        self.visible:bool = data["visible"] # 动态显示状态(false时被折叠)
        self.time:str = data["modules"]["module_author"]["pub_time"] # 动态发布时间
        self.timestamp:int = data["modules"]["module_author"]["pub_ts"] # 动态发布时间戳
        self.jump_url: str = f"https://t.bilibili.com/{self.id}" # 动态跳转链接
        _module_stat: dict[Any, Any] = data["modules"]["module_stat"]
        self.comment_num: int = _module_stat["comment"]["count"] # 评论数
        self.like_num: int = _module_stat["like"]["count"] # 点赞数
        self.forward_num: int = _module_stat["forward"]["count"] # 转发数
        self.tag: str = data.get("modules", {}).get("module_tag", {}).get("text", "") # 置顶


    def get_core_properties_str(self):
        return super().get_core_properties_str()

    def __repr__(self):
        return super().__repr__()


class UPData(BaseData):
    """UP主数据类."""

    def __init__(self, data: dict[Any, Any]):
        """初始化UPData对象.

        Args:
            data(dict): 单条动态信息
        """
        self.raw_data: dict[Any, Any] = data # 原始数据
        author_info: dict[Any, Any] = data["modules"]["module_author"]
        self.uid: int = author_info["mid"] # UP主UID
        self.name: str = author_info["name"] # UP主昵称
        self.face_url: str = author_info["face"] # UP主头像url
        self.jump_url: str = f"https://space.bilibili.com/{self.uid}" # UP主空间链接

    def get_core_properties_str(self):
        return super().get_core_properties_str()

    def __repr__(self):
        return super().__repr__()


class DynamicData(BaseData):
    """动态数据类."""

    def __init__(self, data: dict[Any, Any]):
        """初始化DynamicData对象.

        Args:
            data(dict): 单条动态信息
        """
        self.raw_data: dict[Any, Any] = data # 原始数据
        self.base_info: DynamicBaseData = DynamicBaseData(data) # 动态基础信息
        self.up_info: UPData = UPData(data)

    def get_core_properties_str(self):
        return super().get_core_properties_str()

    def __repr__(self):
        return super().__repr__()