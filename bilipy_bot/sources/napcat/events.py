"""Napcat 事件类型别名.

将 ``Event[*Data]`` 包装为 ``*Event`` 类型别名，用户可直接用作类型注解：

.. code:: python

    from bilipy_bot.sources.napcat.events import NapcatGroupMessageEvent

    @app.subscribe(source.uuid, NapcatType.GROUP_MESSAGE)
    async def handler(event: NapcatGroupMessageEvent):
        print(event.data.group_id)
"""

from typing import TypeAlias

from bilipy_bot.core.event import Event

from .data import (
    NapcatData,
    NapcatFriendAddNoticeData,
    NapcatFriendRecallNoticeData,
    NapcatFriendRequestData,
    NapcatGroupAdminNoticeData,
    NapcatGroupBanNoticeData,
    NapcatGroupCardNoticeData,
    NapcatGroupDecreaseNoticeData,
    NapcatGroupEssenceNoticeData,
    NapcatGroupIncreaseNoticeData,
    NapcatGroupMessageData,
    NapcatGroupMessageSentData,
    NapcatGroupMsgEmojiLikeNoticeData,
    NapcatGroupRecallNoticeData,
    NapcatGroupRequestData,
    NapcatGroupUploadNoticeData,
    NapcatHeartbeatMetaData,
    NapcatHonorNotifyData,
    NapcatLifecycleMetaData,
    NapcatLuckyKingNotifyData,
    NapcatMessageData,
    NapcatMessageSentData,
    NapcatMetaData,
    NapcatNoticeData,
    NapcatNotifyData,
    NapcatPokeNotifyData,
    NapcatPrivateMessageData,
    NapcatPrivateMessageSentData,
    NapcatReactionNoticeData,
    NapcatRequestData,
)

# ── 通配 ──
NapcatEvent: TypeAlias = Event[NapcatData]

# ── 消息事件 ──
NapcatMessageEvent: TypeAlias = Event[NapcatMessageData]
NapcatPrivateMessageEvent: TypeAlias = Event[NapcatPrivateMessageData]
NapcatGroupMessageEvent: TypeAlias = Event[NapcatGroupMessageData]

# ── 消息发送事件 ──
NapcatMessageSentEvent: TypeAlias = Event[NapcatMessageSentData]
NapcatPrivateMessageSentEvent: TypeAlias = Event[NapcatPrivateMessageSentData]
NapcatGroupMessageSentEvent: TypeAlias = Event[NapcatGroupMessageSentData]

# ── 通知事件 ──
NapcatNoticeEvent: TypeAlias = Event[NapcatNoticeData]
NapcatGroupUploadNoticeEvent: TypeAlias = Event[NapcatGroupUploadNoticeData]
NapcatGroupAdminNoticeEvent: TypeAlias = Event[NapcatGroupAdminNoticeData]
NapcatGroupDecreaseNoticeEvent: TypeAlias = Event[NapcatGroupDecreaseNoticeData]
NapcatGroupIncreaseNoticeEvent: TypeAlias = Event[NapcatGroupIncreaseNoticeData]
NapcatGroupBanNoticeEvent: TypeAlias = Event[NapcatGroupBanNoticeData]
NapcatFriendAddNoticeEvent: TypeAlias = Event[NapcatFriendAddNoticeData]
NapcatGroupRecallNoticeEvent: TypeAlias = Event[NapcatGroupRecallNoticeData]
NapcatFriendRecallNoticeEvent: TypeAlias = Event[NapcatFriendRecallNoticeData]
NapcatNotifyEvent: TypeAlias = Event[NapcatNotifyData]
NapcatPokeNotifyEvent: TypeAlias = Event[NapcatPokeNotifyData]
NapcatLuckyKingNotifyEvent: TypeAlias = Event[NapcatLuckyKingNotifyData]
NapcatHonorNotifyEvent: TypeAlias = Event[NapcatHonorNotifyData]
NapcatGroupMsgEmojiLikeNoticeEvent: TypeAlias = Event[NapcatGroupMsgEmojiLikeNoticeData]
NapcatReactionNoticeEvent: TypeAlias = Event[NapcatReactionNoticeData]
NapcatGroupEssenceNoticeEvent: TypeAlias = Event[NapcatGroupEssenceNoticeData]
NapcatGroupCardNoticeEvent: TypeAlias = Event[NapcatGroupCardNoticeData]

# ── 请求事件 ──
NapcatRequestEvent: TypeAlias = Event[NapcatRequestData]
NapcatFriendRequestEvent: TypeAlias = Event[NapcatFriendRequestData]
NapcatGroupRequestEvent: TypeAlias = Event[NapcatGroupRequestData]

# ── 元事件 ──
NapcatMetaEvent: TypeAlias = Event[NapcatMetaData]
NapcatLifecycleMetaEvent: TypeAlias = Event[NapcatLifecycleMetaData]
NapcatHeartbeatMetaEvent: TypeAlias = Event[NapcatHeartbeatMetaData]
