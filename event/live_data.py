from typing import Any, Optional, Literal, Union
import re
from html import unescape
from .base_data import BaseData
from time import time


def _html2_text(text: str) -> str:
    """处理html以及换行符.

    Args:
        text (str): HTML内容

    Returns:
        text (str): 纯文本内容
    """

    # 将<br>标签替换为换行符
    text = re.sub(r'<br\s*/?>', '\n', text)
    ## 将</div>等块级元素替换为换行符(考虑到实际数据结构中较少出现，暂时注释掉)
    #text = re.sub(r'</(p|div|h[1-6]|li|tr)>', '\n', text)
    # 去除其他HTML标签
    text = re.sub(r'<[^>]*>', '', text)
    # 处理HTML实体
    text = unescape(text)
    # 处理多余的空白字符，但保留单个换行符
    text = re.sub(r'[ \t]+', ' ', text)  # 将多个空格或制表符合并为单个空格
    text = re.sub(r' *\n *', '\n', text)  # 去除换行符前后的空格
    text = re.sub(r'\n+', '\n', text).strip()  # 合并多个换行符并去除首尾空白
    return text


class RoomInfo(BaseData):
    """直播间信息类."""

    def __init__(self, room_info: dict[Any, Any]) -> None:
        """初始化RoomInfo对象.

        Args:
            room_info (dict): 直播间信息
        """
        self.raw_data: dict[Any, Any] = room_info  # 原始数据
        self.uid: int = room_info["uid"]  # 用户uid
        self.room_id: int = room_info["room_id"]  # 房间号
        self.title: str = room_info["title"]  # 直播间标题
        self.cover_url: str = room_info["cover"]  # 直播间封面url
        self.background_url: str = room_info["background"]  # 直播间背景图url
        self.description: str = _html2_text(room_info["description"])  # 主播简介
        _tags: str = room_info["tags"]  # 直播间标签，逗号分隔
        self.tags: list = _tags.split(",")  # 直播间标签列表
        self.live_status: int = room_info["live_status"]  # 直播状态 0：未开播 1：直播中 2：轮播中
        self.live_start_time: int = room_info["live_start_time"]  # 直播开始时间戳
        self.parent_area_name: str = room_info["parent_area_name"]  # 直播间父分区
        self.parent_area_id: int = room_info["parent_area_id"]  # 直播间父分区ID
        self.area_name: str = room_info["area_name"]  # 直播间子分区
        self.area_id: int = room_info["area_id"]  # 直播间子分区ID
        self.keyframe_url: str = room_info["keyframe"]  # 直播间关键帧url
        self.online: int = room_info["online"]  # 直播间当前在线人数


class AnchorInfo(BaseData):
    """主播信息类"""

    def __init__(self, anchor_info: dict[Any, Any]):
        """初始化AnchorInfo对象.

        Args:
            anchor_info (dict): 主播信息
        """

        self.raw_data: dict[Any, Any] = anchor_info  # 原始数据
        self.name: str = anchor_info["base_info"]["uname"]  # 主播昵称
        self.face_url: str = anchor_info["base_info"]["face"]  # 主播头像url
        self.gender: str = anchor_info["base_info"]["gender"]  # 主播性别
        self.official_info: dict[Any, Any] = anchor_info["base_info"]["official_info"]["title"]  # 主播官方信息(认证信息)
        self.fanclub_name: str = anchor_info["medal_info"]["medal_name"]  # 粉丝牌名称
        self.fanclub_num: str = anchor_info["medal_info"]["fansclub"]  # 粉丝团人数
        self.live_level: int = anchor_info["live_info"]["level"]  # 主播等级
        self.live_score: int = anchor_info["live_info"]["score"]  # 直播分数
        self.live_upgrade_score: int = anchor_info["live_info"]["upgrade_score"]  # 升级所需分数


class WatchedShow(BaseData):
    """观看榜信息类"""

    def __init__(self, watched_show: dict[Any, Any]):
        """初始化WatchedShow对象.

        Args:
            watched_show (dict): 观看榜信息
        """

        self.raw_data: dict[Any, Any] = watched_show  # 原始数据
        self.switch: bool = watched_show["switch"]  # 观看榜开关
        self.num: int = watched_show["num"]  # 观看人数/人气值
        self.text_small: str = watched_show["text_small"]  # 小文本
        self.text_large: str = watched_show["text_large"]  # 大文本


class NoticeBoard(BaseData):
    """公告栏信息类"""
    raw_data: Optional[dict[Any, Any]] = None
    content: Optional[str] = None
    ctime: Optional[str] = None

    def __init__(self, notice_board: Optional[dict[Any, Any]] = None):
        """初始化NoticeBoard对象.

        Args:
            notice_board (dict): 公告栏信息
        """
        if notice_board is not None:
            self.raw_data = notice_board  # 原始数据
            self.content = notice_board.get("content")  # 公告内容
            self.ctime = notice_board.get("ctime")  # 公告发布时间

    def __getattr__(self, name: str) -> Any:
        if self.raw_data is not None and name in self.raw_data:
            return self.raw_data[name]
        raise AttributeError(f"'NoticeBoard' object has no attribute '{name}'")


class LiveData(BaseData):
    """直播数据类"""

    def __init__(self, data: dict[Any, Any]):
        """初始化LiveInfo对象.

        Args:
            data (dict): API返回数据
        """

        # 直播间信息
        self.raw_data: dict[Any, Any] = data  # 原始数据
        self.room_info: RoomInfo = RoomInfo(data["room_info"])  # 直播间信息
        self.anchor_info: AnchorInfo = AnchorInfo(data["anchor_info"])  # 主播信息
        self.watched_show: WatchedShow = WatchedShow(data["watched_show"])  # 观看榜信息
        self.notice_board: NoticeBoard = NoticeBoard(data["news_info"])  # 公告栏信息

    async def get_live_info(self, status: Literal["open", "close", "opening", "default"]) -> str:
        info = ""
        if status == "open":
            info = f"{self.anchor_info.name}开启了直播《{self.room_info.title}》，当前在线人数为{self.room_info.online}人"
        elif status == "close":
            info = f"{self.anchor_info.name}下播了"
        elif status == "default":
            info = f"{self.anchor_info.name}当前并没有在直播"
        elif status == "opening":
            live_time = int(time()) - self.room_info.live_start_time
            hours, remainder = divmod(live_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            info = f"{self.anchor_info.name}已经直播了{hours}小时{minutes}分钟{seconds}秒，当前在线人数为{self.room_info.online}人"
        return info


if __name__ == "__main__":
    live = LiveData({})  # 实际由回调或其他方式传入
    b = live.room_info
