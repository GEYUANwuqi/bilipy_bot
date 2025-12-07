from typing import Any, Optional
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
    tag: Optional[str] = None

    def __init__(self, data: dict[Any, Any]):
        """初始化DynamicBaseData对象.

        Args:
            data(dict): 单条动态信息
        """

        self.type: str = data["type"] # 动态类型
        self.id: str = data["id_str"] # 动态ID
        self.visible:bool = data["visible"] # 动态显示状态(false时被折叠)
        if self.type == "DYNAMIC_TYPE_DRAW" :
            self.text: str = data["modules"]["module_dynamic"]["major"]["opus"]["summary"]["text"]
        self.time:str = data["modules"]["module_author"]["pub_time"] # 动态发布时间
        self.timestamp:int = data["modules"]["module_author"]["pub_ts"] # 动态发布时间戳
        self.jump_url: str = f"https://t.bilibili.com/{self.id}" # 动态跳转链接
        if data["modules"].get("module_stat", None) is not None:
            _module_stat: dict[Any, Any] = data["modules"]["module_stat"]
            self.comment_num: int = _module_stat["comment"]["count"] # 评论数
            self.like_num: int = _module_stat["like"]["count"] # 点赞数
            self.forward_num: int = _module_stat["forward"]["count"] # 转发数
        if data["modules"].get("module_tag", None) is not None:
            self.tag: str = data["modules"]["module_tag"]["text"] # 置顶


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
        author_info: dict[Any, Any] = data["modules"]["module_author"]
        self.uid: int = author_info["mid"] # UP主UID
        self.name: str = author_info["name"] # UP主昵称
        self.face_url: str = author_info["face"] # UP主头像url
        self.jump_url: str = f"https://space.bilibili.com/{self.uid}" # UP主空间链接

    def get_core_properties_str(self):
        return super().get_core_properties_str()

    def __repr__(self):
        return super().__repr__()


class VideoData(BaseData):
    """视频信息类"""
    raw_data: Optional[dict[Any, Any]] = None
    av_id: Optional[str] = None
    bv_id: Optional[str] = None
    title: Optional[str] = None
    cover_url: Optional[str] = None
    desc: Optional[str] = None
    duration_text: Optional[str] = None
    jump_url: Optional[str] = None
    play_count: Optional[str] = None
    danmaku_count: Optional[str] = None

    def __init__(self, data: Optional[dict[Any, Any]] = None):
        """初始化Video对象.

        Args:
            data (dict): module_dynamic/视频信息
        """
        if data is not None:
            self.raw_data = data  # 原始数据
            video_archive = data["major"]["archive"] # 视频信息
            self.dynamic_text = data["desc"]["text"]
            self.av_id = video_archive.get("aid")  # 视频AV号
            self.bv_id = video_archive.get("bvid")  # 视频BV号
            self.title = video_archive.get("title")  # 视频标题
            self.cover_url = video_archive.get("cover")  # 视频封面
            self.desc = video_archive.get("desc")  # 视频简介
            self.duration_text = video_archive.get("duration_text")  # 视频时长
            self.jump_url = f"www.bilibili.com/video/{self.bv_id}/"  # 视频跳转链接
            stat = video_archive.get("stat", {}) # 互动数据
            self.play_count = stat.get("play")  # 播放数
            self.danmaku_count = stat.get("danmaku")  # 弹幕数


    def get_core_properties_str(self):
        return super().get_core_properties_str()

    def __repr__(self):
        return super().__repr__()


class ForwardData(BaseData):
    """转发动态信息类"""
    raw_data: Optional[dict[Any, Any]] = None
    orig_id: Optional[str] = None
    orig_type: Optional[str] = None
    orig_visible: Optional[bool] = None
    orig_dynamic: Optional['DynamicData'] = None

    def __init__(self, orig: Optional[dict[Any, Any]] = None):
        """初始化Forward对象.

        Args:
            orig (dict): 原始动态信息
        """
        if orig is not None:
            self.raw_data = orig  # 原始数据
            self.orig_id = orig.get("id_str")  # 原动态ID
            self.orig_type = orig.get("type")  # 原动态类型
            self.orig_visible = orig.get("visible")  # 原动态显示状态
            # 可以递归创建原动态对象
            self.orig_dynamic = DynamicData(orig) # 原动态完整信息

    def get_core_properties_str(self):
        return super().get_core_properties_str()

    def __repr__(self):
        return super().__repr__()


class DynamicData(BaseData):
    """动态数据类."""
    video_info: Optional[VideoData] = None
    forward_info: Optional[ForwardData] = None

    def __init__(self, data: dict[Any, Any]):
        """初始化DynamicData对象.

        Args:
            data(dict): 单条动态信息
        """
        self.raw_data: dict[Any, Any] = data # 原始数据
        self.base_info: DynamicBaseData = DynamicBaseData(data) # 动态基础信息
        self.up_info: UPData = UPData(data) # UP主信息
        if data.get("type") == "DYNAMIC_TYPE_AV":
            video_raw = data["modules"]["module_dynamic"]
            self.video_info = VideoData(video_raw)
        if data.get("type") == "DYNAMIC_TYPE_FORWARD":
            forward_raw = data.get("orig")
            self.forward_info = ForwardData(forward_raw)

    def get_core_properties_str(self):
        return super().get_core_properties_str()

    def __repr__(self):
        return super().__repr__()
