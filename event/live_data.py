from typing import Any
import re
from html import unescape


class RoomInfo:
    """直播间信息类.

    Attributes:
        uid(int): 用户uid
        room_id(int): 房间号

    Returns:
        RoomInfo: 直播间信息
    """

    def __init__(self, room_info:dict[Any, Any]) -> None:
        self.uid:int = room_info["uid"] # 用户uid
        self.room_id:int = room_info["room_id"] # 房间号
        self.title:str = room_info["title"] # 直播间标题
        self.cover:str = room_info["cover"] # 直播间封面url
        self.background:str = room_info["background"] # 直播间背景图url
        self.description:str = self._html2_text(room_info["description"]) # 主播简介
        _tags:str = room_info["tags"] # 直播间标签，逗号分隔
        self.tags:list = _tags.split(",") # 直播间标签列表
        self.live_status:int = room_info["live_status"] # 直播状态 0：未开播 1：直播中 2：轮播中
        self.live_start_time:int = room_info["live_start_time"] # 直播开始时间戳
        self.parent_area_name:str = room_info["parent_area_name"] # 直播间父分区
        self.parent_area_id:int = room_info["parent_area_id"] # 直播间父分区ID
        self.area_name:str = room_info["area_name"] # 直播间子分区
        self.area_id:int = room_info["area_id"] # 直播间子分区ID
        self.online:int = room_info["online"] # 直播间当前在线人数

    def _html2_text(self, text:str) -> str:
        """处理html以及换行符.

        Args:
            text (str): HTML内容

        Returns:
            str: 纯文本内容
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


class LiveInfo:
    """直播数据类"""

    def __init__(self, data:dict[Any, Any]):
        """初始化LiveInfo对象.

        Args:
            data (dict): API返回数据
        """

        # 直播间信息
        self.data:dict = data
        self.room_info:RoomInfo = RoomInfo(data.get("room_info", {}))
        self.anchor_info:dict = data.get("anchor_info", {}) # 主播信息
        self.watched_show:dict = data.get("watched_show", {}) # 观看榜信息
        self.medal_name:str = self.anchor_info["medal_info"]["medal_name"] # 粉丝牌名称 anchor_info.medal_info.medal_name
        self.fansclub:str = self.anchor_info["medal_info"]["fansclub"] # 粉丝团人数 anchor_info.medal_info.fansclub

    def __str__(self) -> str:
        return f""
    
a = LiveInfo({})