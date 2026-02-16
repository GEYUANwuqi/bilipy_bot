from typing import Optional
from dataclasses import dataclass

from base_cls import BaseData
from .dto import (
    DynamicDTO,
    AuthorDto,
    StatDto,
    VideoDto,
    MusicDto,
    ArticleDto,
    LiveRcmdDto,
)


def get_max_id(date: dict) -> Optional[int]:
    """获取最新动态的索引ID
    Args:
        date (dict): 原始动态数据
    Returns:
        max_id (int): 索引id，如果数据不存在则返回None

    """
    # 数据校验：检查 items 键是否存在
    if not date or "items" not in date:
        return None

    list_data = date["items"]

    # 数据校验：检查 items 是否为空
    if not list_data:
        return None

    max_timestamp: int = 0
    max_id: Optional[int] = None

    for index, item in enumerate(list_data):
        # 数据校验：检查 item 是否为字典
        if not isinstance(item, dict):
            continue

        # 数据校验：检查嵌套的 key 是否存在
        modules = item.get("modules")
        if not modules or not isinstance(modules, dict):
            continue

        module_author = modules.get("module_author")
        if not module_author or not isinstance(module_author, dict):
            continue

        pub_ts = module_author.get("pub_ts")
        if pub_ts is None:
            continue

        try:
            timestamp = int(pub_ts)
            if timestamp > max_timestamp:
                max_timestamp = timestamp
                max_id = index
        except (ValueError, TypeError):
            # 如果转换失败，跳过该项
            continue

    return max_id


@dataclass(frozen=True)
class AuthorData(BaseData):
    """
    作者信息数据
    """
    uid: int  # UP主UID
    name: str  # UP主昵称
    face: str  # UP主头像URL

    @classmethod
    def from_dto(cls, author: AuthorDto) -> "AuthorData":
        """从AuthorDto构造AuthorData实例"""
        return cls(
            uid=author.uid,
            name=author.name,
            face=author.face,
        )

    @property
    def jump_url(self) -> str:
        """作者空间跳转链接"""
        return f"https://space.bilibili.com/{self.uid}"


@dataclass(frozen=True)
class StatData(BaseData):
    """
    动态统计信息数据
    """
    comment_count: int  # 评论数
    like_count: int  # 点赞数
    forward_count: int  # 转发数

    @classmethod
    def from_dto(cls, stat: StatDto) -> "StatData":
        """从StatDto构造StatData实例"""
        return cls(
            comment_count=stat.comment_count,
            like_count=stat.like_count,
            forward_count=stat.forward_count
        )


@dataclass(frozen=True)
class VideoData(BaseData):
    """
    视频信息数据
    """
    av_id: str  # 视频AV号
    bv_id: str  # 视频BV号
    title: str  # 视频标题
    cover: str  # 视频封面
    desc: str  # 视频简介
    duration_text: str  # 视频时长
    dynamic_text: str  # 动态文本
    play_count: str  # 播放数
    danmaku_count: str  # 弹幕数

    @classmethod
    def from_dto(cls, video: VideoDto) -> "VideoData":
        """从VideoDto构造VideoData实例"""
        return cls(
            av_id=video.av_id,
            bv_id=video.bv_id,
            title=video.title,
            cover=video.cover,
            desc=video.desc,
            duration_text=video.duration_text,
            dynamic_text=video.dynamic_text,
            play_count=video.play_count,
            danmaku_count=video.danmaku_count
        )

    @property
    def jump_url(self) -> str:
        """视频跳转链接"""
        return f"https://www.bilibili.com/video/{self.bv_id}/"


@dataclass(frozen=True)
class MusicData(BaseData):
    """
    音乐信息数据
    """
    music_id: str  # 音乐ID
    title: str  # 音乐标题
    cover: str  # 音乐封面
    label: str  # 音乐标签（作者/歌手）
    dynamic_text: str  # 动态文本

    @classmethod
    def from_dto(cls, music: MusicDto) -> "MusicData":
        """从MusicDto构造MusicData实例"""
        return cls(
            music_id=music.music_id,
            title=music.title,
            cover=music.cover,
            label=music.label,
            dynamic_text=music.dynamic_text
        )

    @property
    def jump_url(self) -> str:
        """音乐跳转链接"""
        return f"https://www.bilibili.com/audio/au{self.music_id}"


@dataclass(frozen=True)
class ArticleData(BaseData):
    """
    专栏信息数据
    """
    title: str  # 专栏标题
    summary: str  # 专栏摘要
    has_more: bool  # 是否有更多内容
    article_id: int  # 专栏ID

    @classmethod
    def from_dto(cls, article: ArticleDto) -> "ArticleData":
        """从ArticleDto构造ArticleData实例"""
        return cls(
            title=article.title,
            summary=article.summary,
            has_more=article.has_more,
            article_id=article.id
        )

    @property
    def jump_url(self) -> str:
        """专栏跳转链接"""
        return f"https://www.bilibili.com/opus/{self.article_id}"


@dataclass(frozen=True)
class LiveRcmdData(BaseData):
    """
    直播推荐信息数据
    """
    room_id: int  # 直播间ID
    live_status: int  # 直播状态 1:直播中
    title: str  # 直播间标题
    cover: str  # 直播间封面
    online: int  # 在线人数
    area_id: int  # 直播分区ID
    area_name: str  # 直播分区
    parent_area_id: int  # 直播父分区ID
    parent_area_name: str  # 直播父分区
    live_start_time: int  # 开播时间戳
    watched_num: Optional[int]  # 观看人数
    switch: Optional[bool]  # 观看榜开关
    text_small: Optional[str]  # 小文本
    text_large: Optional[str]  # 大文本

    @classmethod
    def from_dto(cls, live_rcmd: LiveRcmdDto) -> "LiveRcmdData":
        """从LiveRcmdDto构造LiveRcmdData实例"""
        return cls(
            room_id=live_rcmd.room_id,
            live_status=live_rcmd.live_status,
            title=live_rcmd.title,
            cover=live_rcmd.cover,
            online=live_rcmd.online,
            area_id=live_rcmd.area_id,
            area_name=live_rcmd.area_name,
            parent_area_id=live_rcmd.parent_area_id,
            parent_area_name=live_rcmd.parent_area_name,
            live_start_time=live_rcmd.live_start_time,
            watched_num=live_rcmd.watched_num,
            switch=live_rcmd.switch,
            text_small=live_rcmd.text_small,
            text_large=live_rcmd.text_large
        )

    @property
    def jump_url(self) -> str:
        """直播间跳转链接"""
        return f"https://live.bilibili.com/{self.room_id}"


@dataclass(frozen=True)
class DynamicData(BaseData):
    """
    动态数据
    """
    dynamic_id: str  # 动态ID
    dynamic_type: str  # 动态类型
    visible: bool  # 动态显示状态(false时被折叠)
    pub_time: str  # 发布时间
    pub_ts: int  # 发布时间戳
    author: AuthorData  # 作者信息
    stat: Optional[StatData]  # 统计信息
    tag: Optional[str]  # 标签（如置顶）
    text: Optional[str]  # 文字内容
    pics_url: Optional[list[str]]  # 图片列表
    video: Optional[VideoData]  # 视频信息
    music: Optional[MusicData]  # 音乐信息
    article: Optional[ArticleData]  # 专栏信息
    live_rcmd: Optional[LiveRcmdData]  # 直播推荐信息
    forward_orig: Optional['DynamicData']  # 转发的原动态

    @classmethod
    def from_dto(cls, dto: DynamicDTO) -> "DynamicData":
        """从DTO对象构造DynamicData实例

        Args:
            dto: DynamicDTO对象

        Returns:
            DynamicData实例
        """
        # 构造作者数据
        author_data = AuthorData.from_dto(dto.author)

        # 构造统计数据
        stat_data = StatData.from_dto(dto.stat) if dto.stat else None

        # 构造视频数据
        video_data = VideoData.from_dto(dto.video) if dto.video else None

        # 构造音乐数据
        music_data = MusicData.from_dto(dto.music) if dto.music else None

        # 构造专栏数据
        article_data = ArticleData.from_dto(dto.article) if dto.article else None

        # 构造直播推荐数据
        live_rcmd_data = LiveRcmdData.from_dto(dto.live_rcmd) if dto.live_rcmd else None

        # 递归构造转发动态数据
        forward_orig_data = cls.from_dto(dto.forward_orig) if dto.forward_orig else None

        return cls(
            dynamic_id=dto.dynamic_id,
            dynamic_type=dto.dynamic_type,
            visible=dto.visible,
            pub_time = dto.pub_time,
            pub_ts = dto.pub_ts,
            author=author_data,
            stat=stat_data,
            tag=dto.tag,
            text=dto.text,
            pics_url=dto.pics_url,
            video=video_data,
            music=music_data,
            article=article_data,
            live_rcmd=live_rcmd_data,
            forward_orig=forward_orig_data
        )

    @property
    def jump_url(self) -> str:
        """动态跳转链接"""
        return f"https://t.bilibili.com/{self.dynamic_id}"

    @property
    def is_live(self) -> bool:
        """判断动态是否为直播推荐类型"""
        return self.dynamic_type == "DYNAMIC_TYPE_LIVE_RCMD"

    @property
    def is_video(self) -> bool:
        """判断动态是否为视频类型"""
        return self.dynamic_type == "DYNAMIC_TYPE_AV"

    @property
    def is_music(self) -> bool:
        """判断动态是否为音乐类型"""
        return self.dynamic_type == "DYNAMIC_TYPE_MUSIC"

    @property
    def is_article(self) -> bool:
        """判断动态是否为专栏类型"""
        return self.dynamic_type == "DYNAMIC_TYPE_ARTICLE"

    @property
    def is_word(self) -> bool:
        """判断动态是否为纯文字类型"""
        return self.dynamic_type == "DYNAMIC_TYPE_WORD"

    @property
    def is_draw(self) -> bool:
        """判断动态是否为图文类型"""
        return self.dynamic_type == "DYNAMIC_TYPE_DRAW"

    @property
    def is_forward(self) -> bool:
        """判断动态是否为转发类型"""
        return self.dynamic_type == "DYNAMIC_TYPE_FORWARD"
