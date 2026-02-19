"""
NapCat OneBot11 事件数据模型

基于 OneBot11 协议定义的事件类型，使用 BaseDataModel 实现自动分发构造
"""
from typing import ClassVar, Optional

from base_cls import BaseDataModel
from .segment_data import NapcatMessage


# ==================== 嵌套数据类（发送者信息） ====================

class FriendSender(BaseDataModel):
    """私聊消息发送者信息"""
    user_id: int
    nickname: str
    sex: Optional[str] = None
    age: Optional[int] = None
    group_id: Optional[int] = None  # 群临时会话会有此字段


class GroupSender(BaseDataModel):
    """群消息发送者信息"""
    user_id: int
    nickname: str
    sex: Optional[str] = None
    age: Optional[int] = None
    card: Optional[str] = None  # 群名片/备注
    area: Optional[str] = None  # 地区
    level: Optional[int] = None  # 成员等级
    role: Optional[str] = None  # 角色: owner/admin/member
    title: Optional[str] = None  # 专属头衔


class FileInfo(BaseDataModel):
    """文件信息"""
    id: str
    name: str
    size: int
    busid: int


class EmojiLike(BaseDataModel):
    """表情回应信息"""
    count: int
    emoji_id: int


class HeartbeatStatus(BaseDataModel):
    """心跳状态信息"""
    online: Optional[bool] = None
    good: Optional[bool] = None


# ==================== 事件基类 ====================

class NapcatEvent(BaseDataModel):
    """OneBot11 事件基类

    使用 post_type 字段进行一级分发
    """
    discriminator_field: ClassVar[str] = "post_type"
    time: int
    self_id: int
    post_type: str


# ==================== 消息事件 ====================

class NapcatMessageEvent(NapcatEvent):
    """消息事件基类

    使用 message_type 字段进行二级分发
    """
    discriminator_value: ClassVar[str] = "message"
    discriminator_field: ClassVar[str] = "message_type"
    post_type: str = "message"
    message_type: str
    sub_type: str
    message_id: int
    user_id: int
    message: NapcatMessage
    raw_message: str
    font: int


class NapcatPrivateMessageEvent(NapcatMessageEvent):
    """私聊消息事件"""
    discriminator_value: ClassVar[str] = "private"
    message_type: str = "private"
    sub_type: str = "friend"
    target_id: Optional[int] = None  # 接收者QQ
    temp_source: Optional[int] = None  # 临时会话来源
    sender: FriendSender


class NapcatGroupMessageEvent(NapcatMessageEvent):
    """群消息事件"""
    discriminator_value: ClassVar[str] = "group"
    message_type: str = "group"
    sub_type: str = "normal"  # normal/anonymous/notice
    group_id: int
    sender: GroupSender


# ==================== 消息发送事件（自身消息上报） ====================

class NapcatMessageSentEvent(NapcatEvent):
    """消息发送事件基类（自身发送的消息上报）

    使用 message_type 字段进行二级分发
    """
    discriminator_value: ClassVar[str] = "message_sent"
    discriminator_field: ClassVar[str] = "message_type"
    post_type: str = "message_sent"
    message_type: str
    sub_type: str
    message_id: int
    user_id: int
    message: NapcatMessage
    raw_message: str
    font: int


class NapcatPrivateMessageSentEvent(NapcatMessageSentEvent):
    """私聊消息发送事件"""
    discriminator_value: ClassVar[str] = "private"
    message_type: str = "private"
    sub_type: str = "friend"
    target_id: Optional[int] = None
    sender: FriendSender


class NapcatGroupMessageSentEvent(NapcatMessageSentEvent):
    """群消息发送事件"""
    discriminator_value: ClassVar[str] = "group"
    message_type: str = "group"
    sub_type: str = "normal"
    group_id: int
    sender: GroupSender


# ==================== 通知事件 ====================

class NapcatNoticeEvent(NapcatEvent):
    """通知事件基类

    使用 notice_type 字段进行二级分发
    """
    discriminator_value: ClassVar[str] = "notice"
    discriminator_field: ClassVar[str] = "notice_type"
    post_type: str = "notice"
    notice_type: str


class NapcatGroupUploadNoticeEvent(NapcatNoticeEvent):
    """群文件上传事件"""
    discriminator_value: ClassVar[str] = "group_upload"
    notice_type: str = "group_upload"
    group_id: int
    user_id: int
    file: FileInfo


class NapcatGroupAdminNoticeEvent(NapcatNoticeEvent):
    """群管理员变动事件"""
    discriminator_value: ClassVar[str] = "group_admin"
    notice_type: str = "group_admin"
    sub_type: str  # set/unset
    group_id: int
    user_id: int


class NapcatGroupDecreaseNoticeEvent(NapcatNoticeEvent):
    """群成员减少事件"""
    discriminator_value: ClassVar[str] = "group_decrease"
    notice_type: str = "group_decrease"
    sub_type: str  # leave/kick/kick_me
    group_id: int
    operator_id: int
    user_id: int


class NapcatGroupIncreaseNoticeEvent(NapcatNoticeEvent):
    """群成员增加事件"""
    discriminator_value: ClassVar[str] = "group_increase"
    notice_type: str = "group_increase"
    sub_type: str  # approve/invite
    group_id: int
    operator_id: int
    user_id: int


class NapcatGroupBanNoticeEvent(NapcatNoticeEvent):
    """群禁言事件"""
    discriminator_value: ClassVar[str] = "group_ban"
    notice_type: str = "group_ban"
    sub_type: str  # ban/lift_ban
    group_id: int
    operator_id: int
    user_id: int
    duration: int  # 禁言时长，单位秒


class NapcatFriendAddNoticeEvent(NapcatNoticeEvent):
    """好友添加事件"""
    discriminator_value: ClassVar[str] = "friend_add"
    notice_type: str = "friend_add"
    user_id: int


class NapcatGroupRecallNoticeEvent(NapcatNoticeEvent):
    """群消息撤回事件"""
    discriminator_value: ClassVar[str] = "group_recall"
    notice_type: str = "group_recall"
    group_id: int
    user_id: int
    operator_id: int
    message_id: int


class NapcatFriendRecallNoticeEvent(NapcatNoticeEvent):
    """好友消息撤回事件"""
    discriminator_value: ClassVar[str] = "friend_recall"
    notice_type: str = "friend_recall"
    user_id: int
    message_id: int


class NapcatNotifyEvent(NapcatNoticeEvent):
    """通知事件（戳一戳/运气王/荣誉等）

    使用 sub_type 字段进行三级分发
    """
    discriminator_value: ClassVar[str] = "notify"
    discriminator_field: ClassVar[str] = "sub_type"
    notice_type: str = "notify"
    sub_type: str


class NapcatPokeNotifyEvent(NapcatNotifyEvent):
    """戳一戳事件"""
    discriminator_value: ClassVar[str] = "poke"
    sub_type: str = "poke"
    group_id: Optional[int] = None  # 私聊不存在
    user_id: int
    target_id: int


class NapcatLuckyKingNotifyEvent(NapcatNotifyEvent):
    """运气王事件"""
    discriminator_value: ClassVar[str] = "lucky_king"
    sub_type: str = "lucky_king"
    group_id: int
    user_id: int  # 红包发送者
    target_id: int  # 运气王


class NapcatHonorNotifyEvent(NapcatNotifyEvent):
    """荣誉变更事件"""
    discriminator_value: ClassVar[str] = "honor"
    sub_type: str = "honor"
    group_id: int
    honor_type: str  # talkative/performer/emotion
    user_id: int


class NapcatGroupMsgEmojiLikeNoticeEvent(NapcatNoticeEvent):
    """群表情回应事件（NapCat/LLOneBot）"""
    discriminator_value: ClassVar[str] = "group_msg_emoji_like"
    notice_type: str = "group_msg_emoji_like"
    group_id: int
    user_id: int
    message_id: int
    likes: list[EmojiLike]


class NapcatReactionNoticeEvent(NapcatNoticeEvent):
    """群表情回应事件（Lagrange）"""
    discriminator_value: ClassVar[str] = "reaction"
    notice_type: str = "reaction"
    sub_type: str  # add/remove
    group_id: int
    operator_id: int
    message_id: int
    code: str  # 表情ID
    count: int


class NapcatGroupEssenceNoticeEvent(NapcatNoticeEvent):
    """群精华消息事件"""
    discriminator_value: ClassVar[str] = "essence"
    notice_type: str = "essence"
    sub_type: str  # add/delete
    group_id: int
    message_id: int
    sender_id: int
    operator_id: int


class NapcatGroupCardNoticeEvent(NapcatNoticeEvent):
    """群名片更新事件"""
    discriminator_value: ClassVar[str] = "group_card"
    notice_type: str = "group_card"
    group_id: int
    user_id: int
    card_new: str
    card_old: str


# ==================== 请求事件 ====================

class NapcatRequestEvent(NapcatEvent):
    """请求事件基类

    使用 request_type 字段进行二级分发
    """
    discriminator_value: ClassVar[str] = "request"
    discriminator_field: ClassVar[str] = "request_type"
    post_type: str = "request"
    request_type: str
    flag: str
    user_id: int
    comment: str


class NapcatFriendRequestEvent(NapcatRequestEvent):
    """好友请求事件"""
    discriminator_value: ClassVar[str] = "friend"
    request_type: str = "friend"


class NapcatGroupRequestEvent(NapcatRequestEvent):
    """群请求事件"""
    discriminator_value: ClassVar[str] = "group"
    request_type: str = "group"
    sub_type: str  # add/invite
    group_id: int


# ==================== 元事件 ====================

class NapcatMetaEvent(NapcatEvent):
    """元事件基类

    使用 meta_event_type 字段进行二级分发
    """
    discriminator_value: ClassVar[str] = "meta_event"
    discriminator_field: ClassVar[str] = "meta_event_type"
    post_type: str = "meta_event"
    meta_event_type: str


class NapcatLifecycleMetaEvent(NapcatMetaEvent):
    """生命周期元事件"""
    discriminator_value: ClassVar[str] = "lifecycle"
    meta_event_type: str = "lifecycle"
    sub_type: str  # enable/disable/connect


class NapcatHeartbeatMetaEvent(NapcatMetaEvent):
    """心跳元事件"""
    discriminator_value: ClassVar[str] = "heartbeat"
    meta_event_type: str = "heartbeat"
    status: HeartbeatStatus
    interval: int  # 心跳间隔，单位毫秒
