from typing import Any, Optional
from .base_data import BaseData


def get_max_id(date: dict) -> int:
    """获取最新动态的索引ID
    Args:
        date (dict): 原始动态数据
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
    text: Optional[str] = None
    comment_num: Optional[int] = None
    like_num: Optional[int] = None
    forward_num: Optional[int] = None
    tag: Optional[str] = None

    def __init__(self, data: dict[Any, Any]):
        """初始化DynamicBaseData对象.

        Args:
            data(dict): 单条动态信息
        """

        self.type: str = data["type"] # 动态类型
        self.id: str = data["id_str"] # 动态ID
        self.visible:bool = data["visible"] # 动态显示状态(false时被折叠)
        self.time:str = data["modules"]["module_author"]["pub_time"] # 动态发布时间
        self.timestamp:int = data["modules"]["module_author"]["pub_ts"] # 动态发布时间戳
        self.jump_url: str = f"https://t.bilibili.com/{self.id}" # 动态跳转链接
        if self.type in ["DYNAMIC_TYPE_WORD","DYNAMIC_TYPE_DRAW"] :
            # 文字内容
            self.text = data["modules"]["module_dynamic"]["major"]["opus"]["summary"]["text"]
        if data["modules"].get("module_stat", None) is not None:
            # 互动数据(评论/点赞/转发)
            _module_stat: dict[Any, Any] = data["modules"]["module_stat"]
            self.comment_num = _module_stat["comment"]["count"]
            self.like_num = _module_stat["like"]["count"]
            self.forward_num = _module_stat["forward"]["count"]
        if data["modules"].get("module_tag", None) is not None:
            # 置顶
            self.tag = data["modules"]["module_tag"]["text"]


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


class MusicData(BaseData):
    """音乐信息类"""
    raw_data: Optional[dict[Any, Any]] = None
    music_id: Optional[str] = None
    title: Optional[str] = None
    cover_url: Optional[str] = None
    label: Optional[str] = None
    jump_url: Optional[str] = None
    dynamic_text: Optional[str] = None

    def __init__(self, data: Optional[dict[Any, Any]] = None):
        """初始化Music对象.

        Args:
            data (dict): module_dynamic/音乐信息
        """
        self.raw_data = data  # 原始数据
        music_info = data["major"]["music"]  # 音乐信息
        self.dynamic_text = data.get("desc", {}).get("text", "")  # 动态文本
        self.music_id = music_info.get("id")  # 音乐ID
        self.title = music_info.get("title")  # 音乐标题
        self.cover_url = music_info.get("cover")  # 音乐封面
        self.label = music_info.get("label")  # 音乐标签（作者/歌手）
        self.jump_url = f"https://www.bilibili.com/audio/au{self.music_id}"  # 音乐跳转链接


class ArticleData(BaseData):
    """专栏信息类"""
    raw_data: Optional[dict[Any, Any]] = None
    article_id: Optional[str] = None
    title: Optional[str] = None
    jump_url: Optional[str] = None
    summary: Optional[str] = None
    has_more: Optional[bool] = None

    def __init__(self, data: Optional[dict[Any, Any]] = None, dy_id: str = ""):
        """初始化Article对象.

        Args:
            data (dict): module_dynamic/专栏信息
            dy_id (str): 动态id
        """
        self.raw_data = data  # 原始数据
        opus_info: dict = data["major"]["opus"]  # 专栏信息
        self.title = opus_info.get("title")  # 专栏标题
        self.jump_url = f"https://www.bilibili.com/opus/{dy_id}"  # 专栏跳转链接
        summary_info = opus_info.get("summary")
        self.summary = summary_info.get("text")  # 专栏摘要
        self.has_more = summary_info.get("has_more")  # 是否有更多内容

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
            orig (dict): 被转发动态信息
        """
        self.orig_dynamic = DynamicData(orig) # 直接嵌套


class DynamicData(BaseData):
    """动态数据类."""
    video_info: Optional[VideoData] = None
    music_info: Optional[MusicData] = None
    article_info: Optional[ArticleData] = None
    forward_info: Optional[ForwardData] = None

    def __init__(self, data: dict[Any, Any]):
        """初始化DynamicData对象.

        Args:
            data(dict): 单条动态信息
        """
        self.raw_data: dict[Any, Any] = data # 原始数据
        self.base_info: DynamicBaseData = DynamicBaseData(data) # 动态基础信息
        self.up_info: UPData = UPData(data) # UP主信息

        # 解析视频信息
        if data.get("type") == "DYNAMIC_TYPE_AV":
            video_raw = data["modules"]["module_dynamic"]
            self.video_info = VideoData(video_raw)

        # 解析音乐信息
        if data.get("type") == "DYNAMIC_TYPE_MUSIC":
            music_raw = data["modules"]["module_dynamic"]
            self.music_info = MusicData(music_raw)

        # 解析专栏信息
        if data.get("type") == "DYNAMIC_TYPE_ARTICLE":
            article_raw = data["modules"]["module_dynamic"]
            self.article_info = ArticleData(article_raw, self.base_info.id)

        # 解析转发信息
        if data.get("type") == "DYNAMIC_TYPE_FORWARD":
            forward_raw = data.get("orig")
            self.forward_info = ForwardData(forward_raw)
