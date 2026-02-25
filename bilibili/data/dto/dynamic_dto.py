from logging import getLogger
from typing import Optional, Any, ClassVar
import json
from base_cls import BaseDataModel


_log = getLogger("DynamicDTO")


class AuthorDto(BaseDataModel):
    """
    作者信息DTO
    """
    uid: int  # UP主UID
    name: str  # UP主昵称
    face: str  # UP主头像URL


class StatDto(BaseDataModel):
    """
    动态统计信息DTO
    """
    comment_count: int = 0  # 评论数
    like_count: int = 0  # 点赞数
    forward_count: int = 0  # 转发数


class VideoDto(BaseDataModel):
    """
    视频信息DTO
    """
    av_id: str  # 视频AV号
    bv_id: str  # 视频BV号
    title: str  # 视频标题
    cover: str  # 视频封面
    desc: str  # 视频简介
    duration_text: str  # 视频时长
    play_count: str  # 播放数
    danmaku_count: str  # 弹幕数
    dynamic_text: str = ""  # 动态文本


class MusicDto(BaseDataModel):
    """
    音乐信息DTO
    """
    music_id: str  # 音乐ID
    title: str  # 音乐标题
    cover: str  # 音乐封面
    label: str  # 音乐标签（作者/歌手）
    dynamic_text: str = ""  # 动态文本


class ArticleDto(BaseDataModel):
    """
    专栏信息DTO
    """
    title: str  # 专栏标题
    summary: str  # 专栏摘要
    has_more: bool  # 是否有更多内容
    id: int


class LiveRcmdDto(BaseDataModel):
    """
    直播推荐信息DTO
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
    watched_num: Optional[int] = None  # 观看人数
    switch: Optional[bool] = None  # 观看榜开关
    text_small: Optional[str] = None  # 小文本
    text_large: Optional[str] = None  # 大文本


class DynamicDTO(BaseDataModel):
    """
    动态消息DTO
    """
    discriminator_value: ClassVar[str] = "dynamic"  # 数据类型标识

    dynamic_id: str  # 动态ID
    dynamic_type: str  # 动态类型
    visible: bool  # 动态显示状态(false时被折叠)
    pub_time: str  # 发布时间
    pub_ts: int  # 发布时间戳
    author: AuthorDto  # 作者信息
    tag: Optional[str] = None  # 标签（如置顶）
    text: Optional[str] = None  # 文字内容
    pics_url: Optional[tuple[str, ...]] = None  # 图片列表
    stat: Optional[StatDto] = None  # 统计信息
    video: Optional[VideoDto] = None  # 视频信息
    music: Optional[MusicDto] = None  # 音乐信息
    article: Optional[ArticleDto] = None  # 专栏信息
    live_rcmd: Optional[LiveRcmdDto] = None  # 直播推荐信息
    forward_orig: Optional['DynamicDTO'] = None  # 转发的原动态

    @classmethod
    def from_raw(cls, data: Optional[dict[Any, Any]]) -> "Optional[DynamicDTO]":
        """
        从原始API数据构造DTO对象
        """
        if data is None:
            return None
        try:
            # 基础信息
            dynamic_id = data.get("id_str", "")
            dynamic_type = data.get("type", "")
            visible = data.get("visible", True)
            modules = data.get("modules", {})
            author_info = modules.get("module_author", {})
            pub_time = author_info.get("pub_time", "")
            pub_ts = author_info.get("pub_ts", 0)

            # 动态内容
            text = None
            pics_url = None
            video = None
            music = None
            article = None
            live_rcmd = None

            module_dynamic = modules.get("module_dynamic", {})
            major = module_dynamic.get("major", {})

            # 作者信息
            author = {
                "uid": author_info.get("mid", 0),
                "name": author_info.get("name", ""),
                "face": author_info.get("face", "")
            }

            # 统计信息
            stat = None
            stat_info = modules.get("module_stat")
            if stat_info:
                stat = {
                    "comment_count": stat_info.get("comment", {}).get("count", 0),
                    "like_count": stat_info.get("like", {}).get("count", 0),
                    "forward_count": stat_info.get("forward", {}).get("count", 0)
                }

            # 标签（如置顶）
            tag = None
            if modules.get("module_tag"):
                tag = modules["module_tag"].get("text")

            # 解析文字和图片（DYNAMIC_TYPE_WORD, DYNAMIC_TYPE_DRAW）
            if dynamic_type in ["DYNAMIC_TYPE_WORD", "DYNAMIC_TYPE_DRAW"]:
                opus = major.get("opus", {})
                summary = opus.get("summary", {})
                text = summary.get("text", "")
                pics = opus.get("pics", [])
                if pics:
                    pics_url = tuple(pic.get("url", "") for pic in pics)

            # 解析视频信息
            elif dynamic_type == "DYNAMIC_TYPE_AV":
                archive = major.get("archive", {})
                desc_info = module_dynamic.get("desc", {})
                stat_info_video = archive.get("stat", {})
                video = {
                    "av_id": archive.get("aid", ""),
                    "bv_id": archive.get("bvid", ""),
                    "title": archive.get("title", ""),
                    "cover": archive.get("cover", ""),
                    "desc": archive.get("desc", ""),
                    "duration_text": archive.get("duration_text", ""),
                    "dynamic_text": desc_info.get("text", "") if desc_info else "",
                    "play_count": stat_info_video.get("play"),
                    "danmaku_count": stat_info_video.get("danmaku")
                }

            # 解析音乐信息
            elif dynamic_type == "DYNAMIC_TYPE_MUSIC":
                music_info = major.get("music", {})
                desc_info = module_dynamic.get("desc", {})
                music = {
                    "music_id": str(music_info.get("id", "")),
                    "title": music_info.get("title", ""),
                    "cover": music_info.get("cover", ""),
                    "label": music_info.get("label", ""),
                    "dynamic_text": desc_info.get("text", "") if desc_info else ""
                }

            # 解析专栏信息
            elif dynamic_type == "DYNAMIC_TYPE_ARTICLE":
                opus = major.get("opus", {})
                summary_info = opus.get("summary", {})
                article = {
                    "title": opus.get("title", ""),
                    "summary": summary_info.get("text", ""),
                    "has_more": summary_info.get("has_more", False),
                    "id": int(dynamic_id) if dynamic_id else 0
                }

            # 解析直播推荐信息
            elif dynamic_type == "DYNAMIC_TYPE_LIVE_RCMD":
                live_rcmd_content = major.get("live_rcmd", {}).get("content", "{}")
                live_data = json.loads(live_rcmd_content)
                live_play_info = live_data.get("live_play_info", {})
                watched_show = live_play_info.get("watched_show", {})
                live_rcmd = {
                    "room_id": live_play_info.get("room_id", 0),
                    "live_status": live_play_info.get("live_status", 0),
                    "title": live_play_info.get("title", ""),
                    "cover": live_play_info.get("cover", ""),
                    "online": live_play_info.get("online", 0),
                    "area_id": live_play_info.get("area_id", 0),
                    "area_name": live_play_info.get("area_name", ""),
                    "parent_area_id": live_play_info.get("parent_area_id", 0),
                    "parent_area_name": live_play_info.get("parent_area_name", ""),
                    "live_start_time": live_play_info.get("live_start_time", 0),
                    "watched_num": watched_show.get("num"),
                    "switch": watched_show.get("switch"),
                    "text_small": watched_show.get("text_small"),
                    "text_large": watched_show.get("text_large")
                }

            # 解析转发信息
            forward_orig = None
            if dynamic_type == "DYNAMIC_TYPE_FORWARD":
                orig_data = data.get("orig")
                if orig_data:
                    forward_orig = cls.from_raw(orig_data)

            # 构造标准化字典后使用model_validate
            normalized_data = {
                "dynamic_id": dynamic_id,
                "dynamic_type": dynamic_type,
                "visible": visible,
                "pub_ts": pub_ts,
                "pub_time": pub_time,
                "author": author,
                "stat": stat,
                "tag": tag,
                "text": text,
                "pics_url": pics_url,
                "video": video,
                "music": music,
                "article": article,
                "live_rcmd": live_rcmd,
                "forward_orig": forward_orig
            }

            return cls.model_validate(normalized_data)

        except Exception as e:
            _log.error(f"解析动态数据失败: {e}", exc_info=True)
            return None

    @classmethod
    def from_list(cls, data_dict: list[dict[Any, Any]]) -> "list[Optional[DynamicDTO]]":
        """
        从动态列表数据构造DTO对象列表
        """
        try:
            return [cls.from_raw(data) for data in data_dict]
        except Exception as e:
            _log.error(f"解析动态数据列表失败: {e}", exc_info=True)
            return [None]
