from logging import getLogger
from typing import Optional, Any, ClassVar
import re
from html import unescape
from base_cls import BaseDataModel


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
    # 去除其他HTML标签
    text = re.sub(r'<[^>]*>', '', text)
    # 处理HTML实体
    text = unescape(text)
    # 处理多余的空白字符，但保留单个换行符
    text = re.sub(r'[ \t]+', ' ', text)  # 将多个空格或制表符合并为单个空格
    text = re.sub(r' *\n *', '\n', text)  # 去除换行符前后的空格
    text = re.sub(r'\n+', '\n', text).strip()  # 合并多个换行符并去除首尾空白
    return text


class RoomInfoDto(BaseDataModel):
    """直播间信息DTO"""
    uid: int  # 用户uid
    room_id: int  # 房间号
    title: str  # 直播间标题
    cover_url: str  # 直播间封面url
    background_url: str  # 直播间背景图url
    description: str  # 主播简介
    tags: tuple[str, ...]  # 直播间标签列表
    live_status: int  # 直播状态 0：未开播 1：直播中 2：轮播中
    live_start_time: int  # 直播开始时间戳
    parent_area_name: str  # 直播间父分区
    parent_area_id: int  # 直播间父分区ID
    area_name: str  # 直播间子分区
    area_id: int  # 直播间子分区ID
    keyframe_url: str  # 直播间关键帧url
    online: int  # 直播间当前在线人数


class AnchorInfoDto(BaseDataModel):
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


class WatchedShowDto(BaseDataModel):
    """观看榜信息DTO"""
    switch: bool  # 观看榜开关
    num: int  # 观看人数/人气值
    text_small: str  # 小文本
    text_large: str  # 大文本


class NoticeBoardDto(BaseDataModel):
    """公告栏信息DTO"""
    content: str  # 公告内容
    ctime: str  # 公告发布时间


class LiveRoomDTO(BaseDataModel):
    """直播间数据DTO"""
    discriminator_value: ClassVar[str] = "live_room"  # 数据类型标识

    room_info: RoomInfoDto  # 直播间信息
    anchor_info: AnchorInfoDto  # 主播信息
    watched_show: WatchedShowDto  # 观看榜信息
    notice_board: Optional[NoticeBoardDto] = None  # 公告栏信息

    @classmethod
    def from_raw(cls, data: dict[Any, Any]) -> "Optional[LiveRoomDTO]":
        """从原始API数据构造DTO对象"""
        try:
            # 直播间信息
            room_info_data = data.get("room_info", {})
            _tags: str = room_info_data.get("tags", "")
            tags_tuple = tuple(_tags.split(",")) if _tags else ()

            room_info = {
                "uid": room_info_data.get("uid", 0),
                "room_id": room_info_data.get("room_id", 0),
                "title": room_info_data.get("title", ""),
                "cover_url": room_info_data.get("cover", ""),
                "background_url": room_info_data.get("background", ""),
                "description": _html2_text(room_info_data.get("description", "")),
                "tags": tags_tuple,
                "live_status": room_info_data.get("live_status", 0),
                "live_start_time": room_info_data.get("live_start_time", 0),
                "parent_area_name": room_info_data.get("parent_area_name", ""),
                "parent_area_id": room_info_data.get("parent_area_id", 0),
                "area_name": room_info_data.get("area_name", ""),
                "area_id": room_info_data.get("area_id", 0),
                "keyframe_url": room_info_data.get("keyframe", ""),
                "online": room_info_data.get("online", 0)
            }

            # 主播信息
            anchor_info_data = data.get("anchor_info", {})
            base_info = anchor_info_data.get("base_info", {})
            medal_info = anchor_info_data.get("medal_info", {})
            live_info = anchor_info_data.get("live_info", {})
            official_info = base_info.get("official_info", {})

            anchor_info = {
                "name": base_info.get("uname", ""),
                "face_url": base_info.get("face", ""),
                "gender": base_info.get("gender", ""),
                "official_info": official_info.get("title", ""),
                "fanclub_name": medal_info.get("medal_name", ""),
                "fanclub_num": medal_info.get("fansclub", 0),
                "live_level": live_info.get("level", 0),
                "live_score": live_info.get("score", 0),
                "live_upgrade_score": live_info.get("upgrade_score", 0)
            }

            # 观看榜信息
            watched_show_data = data.get("watched_show", {})
            watched_show = {
                "switch": watched_show_data.get("switch", False),
                "num": watched_show_data.get("num", 0),
                "text_small": watched_show_data.get("text_small", ""),
                "text_large": watched_show_data.get("text_large", "")
            }

            # 公告栏信息
            notice_board = None
            notice_board_data = data.get("news_info")
            if notice_board_data:
                notice_board = {
                    "content": notice_board_data.get("content", ""),
                    "ctime": notice_board_data.get("ctime", "")
                }

            # 构造标准化字典后使用model_validate
            normalized_data = {
                "room_info": room_info,
                "anchor_info": anchor_info,
                "watched_show": watched_show,
                "notice_board": notice_board
            }

            return cls.model_validate(normalized_data)

        except Exception as e:
            _log.error(f"解析直播间数据失败: {e}", exc_info=True)
            return None
