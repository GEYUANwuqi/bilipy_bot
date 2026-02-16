from logging import getLogger
from typing import Optional, Any
import re
from html import unescape
from base_cls import BaseDto


_log = getLogger("LiveRoomDTO")


def _html2_text(text: str) -> str:
    """处理html以及换行符.

    Args:
        text (str): HTML内容

    Returns:
        text (str): 纯文本内容
    """
    # 将<br>标签替换为换行符
    text = re.sub(r'<br\s*/?>', '\n', text)
    # 将</div>等块级元素替换为换行符(考虑到实际数据结构中较少出现，暂时注释掉)
    # text = re.sub(r'</(p|div|h[1-6]|li|tr)>', '\n', text)
    # 去除其他HTML标签
    text = re.sub(r'<[^>]*>', '', text)
    # 处理HTML实体
    text = unescape(text)
    # 处理多余的空白字符，但保留单个换行符
    text = re.sub(r'[ \t]+', ' ', text)  # 将多个空格或制表符合并为单个空格
    text = re.sub(r' *\n *', '\n', text)  # 去除换行符前后的空格
    text = re.sub(r'\n+', '\n', text).strip()  # 合并多个换行符并去除首尾空白
    return text


class RoomInfoDto(BaseDto):
    """直播间信息DTO"""
    uid: int  # 用户uid
    room_id: int  # 房间号
    title: str  # 直播间标题
    cover_url: str  # 直播间封面url
    background_url: str  # 直播间背景图url
    description: str  # 主播简介
    tags: list[str]  # 直播间标签列表
    live_status: int  # 直播状态 0：未开播 1：直播中 2：轮播中
    live_start_time: int  # 直播开始时间戳
    parent_area_name: str  # 直播间父分区
    parent_area_id: int  # 直播间父分区ID
    area_name: str  # 直播间子分区
    area_id: int  # 直播间子分区ID
    keyframe_url: str  # 直播间关键帧url
    online: int  # 直播间当前在线人数

    @classmethod
    def from_dict(cls, room_info: dict[Any, Any]) -> "Optional[RoomInfoDto]":
        """从直播间信息字典构造DTO对象"""
        try:
            _tags: str = room_info.get("tags", "")
            tags_list = _tags.split(",") if _tags else []

            return cls(
                uid=room_info.get("uid", 0),
                room_id=room_info.get("room_id", 0),
                title=room_info.get("title", ""),
                cover_url=room_info.get("cover", ""),
                background_url=room_info.get("background", ""),
                description=_html2_text(room_info.get("description", "")),
                tags=tags_list,
                live_status=room_info.get("live_status", 0),
                live_start_time=room_info.get("live_start_time", 0),
                parent_area_name=room_info.get("parent_area_name", ""),
                parent_area_id=room_info.get("parent_area_id", 0),
                area_name=room_info.get("area_name", ""),
                area_id=room_info.get("area_id", 0),
                keyframe_url=room_info.get("keyframe", ""),
                online=room_info.get("online", 0)
            )
        except Exception as e:
            _log.error(f"解析直播间信息失败: {e}", exc_info=True)
            return None


class AnchorInfoDto(BaseDto):
    """主播信息DTO"""
    name: str  # 主播昵称
    face_url: str  # 主播头像url
    gender: str  # 主播性别
    official_info: str  # 主播官方信息(认证信息)
    fanclub_name: str  # 粉丝牌名称
    fanclub_num: int  # 粉丝团人数
    live_level: int  # 主播等级
    live_score: int  # 直播分数
    live_upgrade_score: int  # 升级所需分数

    @classmethod
    def from_dict(cls, anchor_info: dict[Any, Any]) -> "Optional[AnchorInfoDto]":
        """从主播信息字典构造DTO对象"""
        try:
            base_info = anchor_info.get("base_info", {})
            medal_info = anchor_info.get("medal_info", {})
            live_info = anchor_info.get("live_info", {})
            official_info = base_info.get("official_info", {})

            return cls(
                name=base_info.get("uname", ""),
                face_url=base_info.get("face", ""),
                gender=base_info.get("gender", ""),
                official_info=official_info.get("title", ""),
                fanclub_name=medal_info.get("medal_name", ""),
                fanclub_num=medal_info.get("fansclub", 0),
                live_level=live_info.get("level", 0),
                live_score=live_info.get("score", 0),
                live_upgrade_score=live_info.get("upgrade_score", 0)
            )
        except Exception as e:
            _log.error(f"解析主播信息失败: {e}", exc_info=True)
            return None


class WatchedShowDto(BaseDto):
    """观看榜信息DTO"""
    switch: bool  # 观看榜开关
    num: int  # 观看人数/人气值
    text_small: str  # 小文本
    text_large: str  # 大文本

    @classmethod
    def from_dict(cls, watched_show: dict[Any, Any]) -> "Optional[WatchedShowDto]":
        """从观看榜信息字典构造DTO对象"""
        try:
            return cls(
                switch=watched_show.get("switch", False),
                num=watched_show.get("num", 0),
                text_small=watched_show.get("text_small", ""),
                text_large=watched_show.get("text_large", "")
            )
        except Exception as e:
            _log.error(f"解析观看榜信息失败: {e}", exc_info=True)
            return None


class NoticeBoardDto(BaseDto):
    """公告栏信息DTO"""
    content: str  # 公告内容
    ctime: str  # 公告发布时间

    @classmethod
    def from_dict(cls, notice_board: Optional[dict[Any, Any]]) -> "Optional[NoticeBoardDto]":
        """从公告栏信息字典构造DTO对象"""
        if notice_board is None:
            return None

        try:
            return cls(
                content=notice_board.get("content", ""),
                ctime=notice_board.get("ctime", "")
            )
        except Exception as e:
            _log.error(f"解析公告栏信息失败: {e}", exc_info=True)
            return None


class LiveRoomDTO(BaseDto):
    """直播间数据DTO"""
    room_info: RoomInfoDto  # 直播间信息
    anchor_info: AnchorInfoDto  # 主播信息
    watched_show: WatchedShowDto  # 观看榜信息
    notice_board: Optional[NoticeBoardDto]  # 公告栏信息

    @classmethod
    def from_dict(cls, data: dict[Any, Any]) -> "Optional[LiveRoomDTO]":
        """从API返回数据字典构造DTO对象"""
        try:
            room_info = RoomInfoDto.from_dict(data.get("room_info", {}))
            anchor_info = AnchorInfoDto.from_dict(data.get("anchor_info", {}))
            watched_show = WatchedShowDto.from_dict(data.get("watched_show", {}))
            notice_board = NoticeBoardDto.from_dict(data.get("news_info"))

            if room_info is None or anchor_info is None or watched_show is None:
                _log.error("解析直播间数据失败: 必要字段缺失")
                return None

            return cls(
                room_info=room_info,
                anchor_info=anchor_info,
                watched_show=watched_show,
                notice_board=notice_board
            )
        except Exception as e:
            _log.error(f"解析直播间数据失败: {e}", exc_info=True)
            return None
