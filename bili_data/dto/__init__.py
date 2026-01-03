from .danmaku_msg_dto import (
    DanmakuMsgDTO,
    MedalInfoDto,
    UserInfoDto
)
from .danmaku_gift_dto import (
    DanmakuGiftDTO,
    BlindGiftInfoDto,
    GiftMedalInfoDto,
    GiftInfoDto,
    GiftSenderDto,
    GiftReceiverDto,
)
from .dynamic_dto import (
    DynamicDTO,
    AuthorDto,
    StatDto,
    VideoDto,
    MusicDto,
    ArticleDto,
    LiveRcmdDto,
)

#  TODO: pydantic BaseModel版本的DTO
__all__ = [
    "DanmakuMsgDTO",
    "MedalInfoDto",
    "UserInfoDto",
    "DanmakuGiftDTO",
    "BlindGiftInfoDto",
    "GiftMedalInfoDto",
    "GiftInfoDto",
    "GiftSenderDto",
    "GiftReceiverDto",
    "DynamicDTO",
    "AuthorDto",
    "StatDto",
    "VideoDto",
    "MusicDto",
    "ArticleDto",
    "LiveRcmdDto",
]
