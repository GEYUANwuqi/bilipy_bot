"""
NapCat OneBot11 事件数据模型

基于 OneBot11 协议定义的事件类型，使用 BaseDataModel 实现自动分发构造
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import PrivateAttr

from butterbot.core.data import BaseDataModel

if TYPE_CHECKING:
    from butterbot.core.context import AppContext
    from butterbot.core.event import EventBus

    from ..api import NapcatApi

from ..types import NapcatType
from .segment_data import NapcatMessage

NapcatMessageInput = str | list[dict[str, Any]] | NapcatMessage


def _message_payload(
    message: NapcatMessageInput,
    *,
    reply_to: int | None = None,
) -> list[dict[str, Any]] | NapcatMessage:
    """将便捷方法接受的消息转换为 NapCat API 可接受的格式。"""
    if reply_to is None and not isinstance(message, str):
        return message

    segments: list[dict[str, Any]] = []
    if reply_to is not None:
        segments.append({"type": "reply", "data": {"id": str(reply_to)}})

    if isinstance(message, str):
        segments.append({"type": "text", "data": {"text": message}})
    elif isinstance(message, NapcatMessage):
        segments.extend(message.to_list_dict())
    else:
        segments.extend(message)
    return segments


# ==================== 嵌套数据类（发送者信息） ====================


class FriendSender(BaseDataModel):
    """私聊消息发送者信息"""

    user_id: int
    nickname: str
    sex: str | None = None
    age: int | None = None
    group_id: int | None = None  # 群临时会话会有此字段


class GroupSender(BaseDataModel):
    """群消息发送者信息"""

    user_id: int
    nickname: str
    sex: str | None = None
    age: int | None = None
    card: str | None = None  # 群名片/备注
    area: str | None = None  # 地区
    level: int | None = None  # 成员等级
    role: str | None = None  # 角色: owner/admin/member
    title: str | None = None  # 专属头衔


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

    online: bool | None = None
    good: bool | None = None


# ==================== 事件基类 ====================


class NapcatData(BaseDataModel):
    """OneBot11 事件基类

    使用 post_type 字段进行一级分发
    """

    discriminator_field: ClassVar[str] = "post_type"
    event_type: ClassVar[NapcatType] = NapcatType.UNKNOWN
    time: int
    self_id: int
    post_type: str

    _runtime: AppContext | None = PrivateAttr(default=None)
    _config_key: str | None = PrivateAttr(default=None)

    def bind_runtime(self, runtime: AppContext, config_key: str) -> None:
        """绑定产生该事件的应用上下文。"""
        object.__setattr__(self, "_runtime", runtime)
        object.__setattr__(self, "_config_key", config_key)

    @property
    def runtime(self) -> AppContext:
        """获取已绑定的应用上下文。"""
        if self._runtime is None:
            raise RuntimeError("NapcatData 尚未绑定 runtime")
        return self._runtime

    @property
    def config_key(self) -> str:
        """获取产生该事件的 NapCat 配置键。"""
        if self._config_key is None:
            raise RuntimeError("NapcatData 尚未绑定 config_key")
        return self._config_key

    @property
    def bus(self) -> EventBus:
        """获取应用事件总线。"""
        return self.runtime.bus

    @property
    def api(self) -> NapcatApi:
        """获取产生该事件的 NapCat API 实例。"""
        # 局部导入避免 NapcatApi -> data -> NapcatApi 循环依赖。
        from ..api import NapcatApi

        return self.runtime.api_ctx.get(NapcatApi, self.config_key)


# ==================== 消息事件 ====================


class NapcatMessageData(NapcatData):
    """消息事件基类

    使用 message_type 字段进行二级分发
    """

    discriminator_value: ClassVar[str] = "message"
    discriminator_field: ClassVar[str] = "message_type"
    event_type: ClassVar[NapcatType] = NapcatType.MESSAGE
    post_type: str = "message"
    message_type: str
    sub_type: str
    message_id: int
    user_id: int
    message: NapcatMessage
    raw_message: str
    font: int

    async def recall(self) -> dict | None:
        """撤回该消息。"""
        return await self.api.delete_message(self.message_id)

    async def set_emoji_like(
        self,
        emoji_id: str | int,
        *,
        enabled: bool = True,
    ) -> dict | None:
        """设置或取消该消息的表情回应。"""
        return await self.api.set_message_emoji_like(
            self.message_id,
            str(emoji_id),
            set=enabled,
        )


class NapcatPrivateMessageData(NapcatMessageData):
    """私聊消息事件"""

    discriminator_value: ClassVar[str] = "private"
    event_type: ClassVar[NapcatType] = NapcatType.PRIVATE_MESSAGE
    message_type: str = "private"
    sub_type: str = "friend"
    target_id: int | None = None  # 接收者QQ
    temp_source: int | None = None  # 临时会话来源
    sender: FriendSender

    async def reply(
        self,
        message: NapcatMessageInput,
        *,
        quote: bool = True,
    ) -> dict | None:
        """回复该私聊消息。"""
        payload = _message_payload(
            message,
            reply_to=self.message_id if quote else None,
        )
        return await self.api.send_private_message(self.user_id, payload)

    async def mark_read(self) -> dict | None:
        """将与该用户的私聊消息标记为已读。"""
        return await self.api.mark_private_messages_as_read(self.user_id)

    async def poke(self) -> dict | None:
        """戳一戳该私聊消息的发送者。"""
        return await self.api.friend_poke(self.user_id)

    async def like(self, times: int = 1) -> dict | None:
        """给该私聊消息的发送者点赞。"""
        return await self.api.send_like(self.user_id, times=times)


class NapcatGroupMessageData(NapcatMessageData):
    """群消息事件"""

    discriminator_value: ClassVar[str] = "group"
    event_type: ClassVar[NapcatType] = NapcatType.GROUP_MESSAGE
    message_type: str = "group"
    sub_type: str = "normal"  # normal/anonymous/notice
    group_id: int
    sender: GroupSender

    async def reply(
        self,
        message: NapcatMessageInput,
        *,
        quote: bool = True,
    ) -> dict | None:
        """回复该群消息。"""
        payload = _message_payload(
            message,
            reply_to=self.message_id if quote else None,
        )
        return await self.api.send_group_message(self.group_id, payload)

    async def mark_read(self) -> dict | None:
        """将该群的消息标记为已读。"""
        return await self.api.mark_group_messages_as_read(self.group_id)

    async def poke(self, user_id: int | None = None) -> dict | None:
        """在群内戳一戳指定用户，默认为消息发送者。"""
        target_id = self.user_id if user_id is None else user_id
        return await self.api.send_poke(self.group_id, target_id)


# ==================== 消息发送事件（自身消息上报） ====================


class NapcatMessageSentData(NapcatData):
    """消息发送事件基类（自身发送的消息上报）

    使用 message_type 字段进行二级分发
    """

    discriminator_value: ClassVar[str] = "message_sent"
    discriminator_field: ClassVar[str] = "message_type"
    event_type: ClassVar[NapcatType] = NapcatType.SENT
    post_type: str = "message_sent"
    message_type: str
    sub_type: str
    message_id: int
    user_id: int
    message: NapcatMessage
    raw_message: str
    font: int


class NapcatPrivateMessageSentData(NapcatMessageSentData):
    """私聊消息发送事件"""

    discriminator_value: ClassVar[str] = "private"
    event_type: ClassVar[NapcatType] = NapcatType.PRIVATE_SENT
    message_type: str = "private"
    sub_type: str = "friend"
    target_id: int | None = None
    sender: FriendSender


class NapcatGroupMessageSentData(NapcatMessageSentData):
    """群消息发送事件"""

    discriminator_value: ClassVar[str] = "group"
    event_type: ClassVar[NapcatType] = NapcatType.GROUP_SENT
    message_type: str = "group"
    sub_type: str = "normal"
    group_id: int
    sender: GroupSender


# ==================== 通知事件 ====================


class NapcatNoticeData(NapcatData):
    """通知事件基类

    使用 notice_type 字段进行二级分发
    """

    discriminator_value: ClassVar[str] = "notice"
    discriminator_field: ClassVar[str] = "notice_type"
    event_type: ClassVar[NapcatType] = NapcatType.NOTICE
    post_type: str = "notice"
    notice_type: str


class NapcatGroupUploadNoticeData(NapcatNoticeData):
    """群文件上传事件"""

    discriminator_value: ClassVar[str] = "group_upload"
    event_type: ClassVar[NapcatType] = NapcatType.GROUP_UPLOAD_NOTICE
    notice_type: str = "group_upload"
    group_id: int
    user_id: int
    file: FileInfo


class NapcatGroupAdminNoticeData(NapcatNoticeData):
    """群管理员变动事件"""

    discriminator_value: ClassVar[str] = "group_admin"
    event_type: ClassVar[NapcatType] = NapcatType.GROUP_ADMIN_NOTICE
    notice_type: str = "group_admin"
    sub_type: str  # set/unset
    group_id: int
    user_id: int


class NapcatGroupDecreaseNoticeData(NapcatNoticeData):
    """群成员减少事件"""

    discriminator_value: ClassVar[str] = "group_decrease"
    event_type: ClassVar[NapcatType] = NapcatType.GROUP_DECREASE_NOTICE
    notice_type: str = "group_decrease"
    sub_type: str  # leave/kick/kick_me
    group_id: int
    operator_id: int
    user_id: int


class NapcatGroupIncreaseNoticeData(NapcatNoticeData):
    """群成员增加事件"""

    discriminator_value: ClassVar[str] = "group_increase"
    event_type: ClassVar[NapcatType] = NapcatType.GROUP_INCREASE_NOTICE
    notice_type: str = "group_increase"
    sub_type: str  # approve/invite
    group_id: int
    operator_id: int
    user_id: int


class NapcatGroupBanNoticeData(NapcatNoticeData):
    """群禁言事件"""

    discriminator_value: ClassVar[str] = "group_ban"
    event_type: ClassVar[NapcatType] = NapcatType.GROUP_BAN_NOTICE
    notice_type: str = "group_ban"
    sub_type: str  # ban/lift_ban
    group_id: int
    operator_id: int
    user_id: int
    duration: int  # 禁言时长，单位秒


class NapcatFriendAddNoticeData(NapcatNoticeData):
    """好友添加事件"""

    discriminator_value: ClassVar[str] = "friend_add"
    event_type: ClassVar[NapcatType] = NapcatType.FRIEND_ADD_NOTICE
    notice_type: str = "friend_add"
    user_id: int


class NapcatGroupRecallNoticeData(NapcatNoticeData):
    """群消息撤回事件"""

    discriminator_value: ClassVar[str] = "group_recall"
    event_type: ClassVar[NapcatType] = NapcatType.GROUP_RECALL_NOTICE
    notice_type: str = "group_recall"
    group_id: int
    user_id: int
    operator_id: int
    message_id: int


class NapcatFriendRecallNoticeData(NapcatNoticeData):
    """好友消息撤回事件"""

    discriminator_value: ClassVar[str] = "friend_recall"
    event_type: ClassVar[NapcatType] = NapcatType.FRIEND_RECALL_NOTICE
    notice_type: str = "friend_recall"
    user_id: int
    message_id: int


class NapcatNotifyData(NapcatNoticeData):
    """通知事件（戳一戳/运气王/荣誉等）

    使用 sub_type 字段进行三级分发
    """

    discriminator_value: ClassVar[str] = "notify"
    discriminator_field: ClassVar[str] = "sub_type"
    event_type: ClassVar[NapcatType] = NapcatType.NOTICE
    notice_type: str = "notify"
    sub_type: str


class NapcatPokeNotifyData(NapcatNotifyData):
    """戳一戳事件"""

    discriminator_value: ClassVar[str] = "poke"
    event_type: ClassVar[NapcatType] = NapcatType.POKE_NOTIFY
    sub_type: str = "poke"
    group_id: int | None = None  # 私聊不存在
    user_id: int
    target_id: int

    async def poke_back(self) -> dict | None:
        """戳回事件发起者。"""
        if self.group_id is None:
            return await self.api.friend_poke(self.user_id)
        return await self.api.send_poke(self.group_id, self.user_id)


class NapcatLuckyKingNotifyData(NapcatNotifyData):
    """运气王事件"""

    discriminator_value: ClassVar[str] = "lucky_king"
    event_type: ClassVar[NapcatType] = NapcatType.LUCKY_KING_NOTIFY
    sub_type: str = "lucky_king"
    group_id: int
    user_id: int  # 红包发送者
    target_id: int  # 运气王


class NapcatHonorNotifyData(NapcatNotifyData):
    """荣誉变更事件"""

    discriminator_value: ClassVar[str] = "honor"
    event_type: ClassVar[NapcatType] = NapcatType.HONOR_NOTIFY
    sub_type: str = "honor"
    group_id: int
    honor_type: str  # talkative/performer/emotion
    user_id: int


class NapcatGroupMsgEmojiLikeNoticeData(NapcatNoticeData):
    """群表情回应事件（NapCat/LLOneBot）"""

    discriminator_value: ClassVar[str] = "group_msg_emoji_like"
    event_type: ClassVar[NapcatType] = NapcatType.GROUP_EMOJI_LIKE_NOTICE
    notice_type: str = "group_msg_emoji_like"
    group_id: int
    user_id: int
    message_id: int
    likes: list[EmojiLike]


class NapcatReactionNoticeData(NapcatNoticeData):
    """群表情回应事件（Lagrange）"""

    discriminator_value: ClassVar[str] = "reaction"
    event_type: ClassVar[NapcatType] = NapcatType.REACTION_NOTICE
    notice_type: str = "reaction"
    sub_type: str  # add/remove
    group_id: int
    operator_id: int
    message_id: int
    code: str  # 表情ID
    count: int


class NapcatGroupEssenceNoticeData(NapcatNoticeData):
    """群精华消息事件"""

    discriminator_value: ClassVar[str] = "essence"
    event_type: ClassVar[NapcatType] = NapcatType.GROUP_ESSENCE_NOTICE
    notice_type: str = "essence"
    sub_type: str  # add/delete
    group_id: int
    message_id: int
    sender_id: int
    operator_id: int


class NapcatGroupCardNoticeData(NapcatNoticeData):
    """群名片更新事件"""

    discriminator_value: ClassVar[str] = "group_card"
    event_type: ClassVar[NapcatType] = NapcatType.GROUP_CARD_NOTICE
    notice_type: str = "group_card"
    group_id: int
    user_id: int
    card_new: str
    card_old: str


# ==================== 请求事件 ====================


class NapcatRequestData(NapcatData):
    """请求事件基类

    使用 request_type 字段进行二级分发
    """

    discriminator_value: ClassVar[str] = "request"
    discriminator_field: ClassVar[str] = "request_type"
    event_type: ClassVar[NapcatType] = NapcatType.REQUEST
    post_type: str = "request"
    request_type: str
    flag: str
    user_id: int
    comment: str


class NapcatFriendRequestData(NapcatRequestData):
    """好友请求事件"""

    discriminator_value: ClassVar[str] = "friend"
    event_type: ClassVar[NapcatType] = NapcatType.FRIEND_REQUEST
    request_type: str = "friend"

    async def approve(self, remark: str = "") -> dict | None:
        """同意好友请求。"""
        return await self.api.set_friend_add_request(
            self.flag,
            approve=True,
            remark=remark,
        )

    async def reject(self) -> dict | None:
        """拒绝好友请求。"""
        return await self.api.set_friend_add_request(self.flag, approve=False)


class NapcatGroupRequestData(NapcatRequestData):
    """群请求事件"""

    discriminator_value: ClassVar[str] = "group"
    event_type: ClassVar[NapcatType] = NapcatType.GROUP_REQUEST
    request_type: str = "group"
    sub_type: str  # add/invite
    group_id: int

    async def approve(self) -> dict | None:
        """同意加群申请或邀请。"""
        return await self.api.set_group_add_request(
            self.flag,
            self.sub_type,
            approve=True,
        )

    async def reject(self, reason: str = "") -> dict | None:
        """拒绝加群申请或邀请。"""
        return await self.api.set_group_add_request(
            self.flag,
            self.sub_type,
            approve=False,
            reason=reason,
        )


# ==================== 元事件 ====================


class NapcatMetaData(NapcatData):
    """元事件基类

    使用 meta_event_type 字段进行二级分发
    """

    discriminator_value: ClassVar[str] = "meta_event"
    discriminator_field: ClassVar[str] = "meta_event_type"
    event_type: ClassVar[NapcatType] = NapcatType.META
    post_type: str = "meta_event"
    meta_event_type: str


class NapcatLifecycleMetaData(NapcatMetaData):
    """生命周期元事件"""

    discriminator_value: ClassVar[str] = "lifecycle"
    event_type: ClassVar[NapcatType] = NapcatType.LIFECYCLE_META
    meta_event_type: str = "lifecycle"
    sub_type: str  # enable/disable/connect


class NapcatHeartbeatMetaData(NapcatMetaData):
    """心跳元事件"""

    discriminator_value: ClassVar[str] = "heartbeat"
    event_type: ClassVar[NapcatType] = NapcatType.HEARTBEAT_META
    meta_event_type: str = "heartbeat"
    status: HeartbeatStatus
    interval: int  # 心跳间隔，单位毫秒
