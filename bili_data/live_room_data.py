from typing import Optional
from dataclasses import dataclass
from time import time

from .base_data import BaseData
from .dto import (
    LiveRoomDTO,
    RoomInfoDto,
    AnchorInfoDto,
    WatchedShowDto,
    NoticeBoardDto,
)
from utils import LiveType


@dataclass(frozen=True)
class RoomInfoData(BaseData):
    """直播间信息数据"""
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
    def from_dto(cls, room_info: RoomInfoDto) -> "RoomInfoData":
        """从RoomInfoDto构造RoomInfoData实例"""
        return cls(
            uid=room_info.uid,
            room_id=room_info.room_id,
            title=room_info.title,
            cover_url=room_info.cover_url,
            background_url=room_info.background_url,
            description=room_info.description,
            tags=room_info.tags,
            live_status=room_info.live_status,
            live_start_time=room_info.live_start_time,
            parent_area_name=room_info.parent_area_name,
            parent_area_id=room_info.parent_area_id,
            area_name=room_info.area_name,
            area_id=room_info.area_id,
            keyframe_url=room_info.keyframe_url,
            online=room_info.online
        )

    @property
    def jump_url(self) -> str:
        """直播间跳转链接"""
        return f"https://live.bilibili.com/{self.room_id}"


@dataclass(frozen=True)
class AnchorInfoData(BaseData):
    """主播信息数据"""
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
    def from_dto(cls, anchor_info: AnchorInfoDto) -> "AnchorInfoData":
        """从AnchorInfoDto构造AnchorInfoData实例"""
        return cls(
            name=anchor_info.name,
            face_url=anchor_info.face_url,
            gender=anchor_info.gender,
            official_info=anchor_info.official_info,
            fanclub_name=anchor_info.fanclub_name,
            fanclub_num=anchor_info.fanclub_num,
            live_level=anchor_info.live_level,
            live_score=anchor_info.live_score,
            live_upgrade_score=anchor_info.live_upgrade_score
        )


@dataclass(frozen=True)
class WatchedShowData(BaseData):
    """观看榜信息数据"""
    switch: bool  # 观看榜开关
    num: int  # 观看人数/人气值
    text_small: str  # 小文本
    text_large: str  # 大文本

    @classmethod
    def from_dto(cls, watched_show: WatchedShowDto) -> "WatchedShowData":
        """从WatchedShowDto构造WatchedShowData实例"""
        return cls(
            switch=watched_show.switch,
            num=watched_show.num,
            text_small=watched_show.text_small,
            text_large=watched_show.text_large
        )


@dataclass(frozen=True)
class NoticeBoardData(BaseData):
    """公告栏信息数据"""
    content: str  # 公告内容
    ctime: str  # 公告发布时间

    @classmethod
    def from_dto(cls, notice_board: NoticeBoardDto) -> "NoticeBoardData":
        """从NoticeBoardDto构造NoticeBoardData实例"""
        return cls(
            content=notice_board.content,
            ctime=notice_board.ctime
        )


@dataclass(frozen=True)
class LiveRoomData(BaseData):
    """直播间数据"""
    room_info: RoomInfoData  # 直播间信息
    anchor_info: AnchorInfoData  # 主播信息
    watched_show: WatchedShowData  # 观看榜信息
    notice_board: Optional[NoticeBoardData]  # 公告栏信息

    @classmethod
    def from_dto(cls, dto: LiveRoomDTO) -> "LiveRoomData":
        """从DTO对象构造LiveRoomData实例

        Args:
            dto: LiveRoomDTO对象

        Returns:
            LiveRoomData实例
        """
        # 构造直播间信息数据
        room_info_data = RoomInfoData.from_dto(dto.room_info)

        # 构造主播信息数据
        anchor_info_data = AnchorInfoData.from_dto(dto.anchor_info)

        # 构造观看榜信息数据
        watched_show_data = WatchedShowData.from_dto(dto.watched_show)

        # 构造公告栏信息数据
        notice_board_data = NoticeBoardData.from_dto(dto.notice_board) if dto.notice_board else None

        return cls(
            room_info=room_info_data,
            anchor_info=anchor_info_data,
            watched_show=watched_show_data,
            notice_board=notice_board_data
        )

    async def get_live_info(self, status: LiveType) -> str:
        """根据直播状态获取直播信息文本

        Args:
            status: 直播状态

        Returns:
            直播信息文本
        """
        info = ""
        if status == LiveType.OPEN:
            info = f"{self.anchor_info.name}开启了直播《{self.room_info.title}》，快速链接：{self.room_info.jump_url}"
        elif status == LiveType.CLOSE:
            info = f"{self.anchor_info.name}下播了"
        elif status == LiveType.OFFLINE:
            info = f"{self.anchor_info.name}当前并没有在直播"
        elif status == LiveType.ONLINE:
            live_time = int(time()) - self.room_info.live_start_time
            hours, remainder = divmod(live_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            info = f"{self.anchor_info.name}已经直播了{hours}小时{minutes}分钟{seconds}秒，当前在线人数为{self.room_info.online}人"
        return info
