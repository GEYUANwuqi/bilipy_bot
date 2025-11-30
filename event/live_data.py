from typing import Any
import re
from html import unescape


class RoomInfo:
    """直播间信息类.

    Attributes:
        uid(int): 用户uid
        room_id(int): 房间号
    """

    def __init__(self, room_info: dict[Any, Any]) -> None:
        """初始化RoomInfo对象.

        Args:
            room_info (dict): 直播间信息
        """
        self.data: dict[Any, Any] = room_info # 原始数据
        self.uid: int = room_info["uid"] # 用户uid
        self.room_id: int = room_info["room_id"] # 房间号
        self.title: str = room_info["title"] # 直播间标题
        self.cover_url: str = room_info["cover"] # 直播间封面url
        self.background_url: str = room_info["background"] # 直播间背景图url
        self.description: str = self._html2_text(room_info["description"]) # 主播简介
        _tags: str = room_info["tags"] # 直播间标签，逗号分隔
        self.tags: list = _tags.split(",") # 直播间标签列表
        self.live_status: int = room_info["live_status"] # 直播状态 0：未开播 1：直播中 2：轮播中
        self.live_start_time: int = room_info["live_start_time"] # 直播开始时间戳
        self.parent_area_name: str = room_info["parent_area_name"] # 直播间父分区
        self.parent_area_id: int = room_info["parent_area_id"] # 直播间父分区ID
        self.area_name: str = room_info["area_name"] # 直播间子分区
        self.area_id: int = room_info["area_id"] # 直播间子分区ID
        self.keyframe_url: str = room_info["keyframe"] # 直播间关键帧url
        self.online: int = room_info["online"] # 直播间当前在线人数

    def _html2_text(self, text: str) -> str:
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

    def __str__(self) -> str:
        return f""

class AnchorInfo:
    """主播信息类"""

    def __init__(self, anchor_info: dict[Any, Any]):
        """初始化AnchorInfo对象.

        Args:
            anchor_info (dict): 主播信息
        """

        self.data: dict[Any, Any] = anchor_info # 原始数据
        self.name: str = anchor_info["base_info"]["uname"] # 主播昵称
        self.face_url: str = anchor_info["base_info"]["face"] # 主播头像url
        self.gender: str = anchor_info["base_info"]["gender"] # 主播性别
        self.fansclub_name: str = anchor_info["medal_info"]["medal_name"] # 粉丝牌名称
        self.fansclub_num: str = anchor_info["medal_info"]["fansclub"] # 粉丝团人数

    def __str__(self) -> str:
        return f""

class WatchedShow:
    """观看榜信息类"""

    def __init__(self, watched_show: dict[Any, Any]):
        """初始化WatchedShow对象.

        Args:
            watched_show (dict): 观看榜信息
        """

        self.data: dict[Any, Any] = watched_show # 原始数据
        self.num: int = watched_show["num"] # 观看人数
        self.text_small: str = watched_show["text_small"] # 小文本
        self.text_large: str = watched_show["text_large"] # 大文本
    
    def __str__(self) -> str:
        return f""

class NoticeBoard:
    """公告栏信息类"""

    def __init__(self, notice_board: dict[Any, Any]):
        """初始化NoticeBoard对象.

        Args:
            notice_board (dict): 公告栏信息
        """

        self.data: dict[Any, Any] = notice_board # 原始数据
        self.uid: int = notice_board["uid"] # 公告uid
        self.content: str = notice_board["content"] # 公告内容
        self.ctime: str = notice_board["ctime"] # 公告发布时间

    def __str__(self) -> str:
        return f""

class LiveData:
    """直播数据类"""

    def __init__(self, data: dict[Any, Any]):
        """初始化LiveInfo对象.

        Args:
            data (dict): API返回数据
        """

        # 直播间信息
        self.data: dict[Any, Any] = data # 原始数据
        self.room_info: RoomInfo = RoomInfo(data["room_info"]) # 直播间信息
        self.anchor_info: AnchorInfo = AnchorInfo(data["anchor_info"]) # 主播信息
        self.watched_show: WatchedShow = WatchedShow(data["watched_show"]) # 观看榜信息
        self.notice_board: NoticeBoard = NoticeBoard(data["news_info"]) # 公告栏信息


    def __str__(self) -> str:
        return f""

info = LiveData({}) # 实际由回调或其他方式传入
b = info.room_info.online