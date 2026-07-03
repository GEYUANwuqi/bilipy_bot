from typing import Any

from bilipy_bot.core.types import BaseType


class NapcatType(BaseType):
    """NapCat 事件类型枚举.

    按 OneBot 协议 `post_type` → 二级字段组织层级结构：

    - ``napcat.meta``: 元事件（lifecycle / heartbeat）
    - ``napcat.message``: 消息事件（group / private）
    - ``napcat.sent``: 自身消息事件（group / private）
    - ``napcat.request``: 请求事件（friend / group）
    - ``napcat.notice``: 通知事件（group_upload / poke / …）

    大类（如 ``MESSAGE``）可匹配下属所有子类，
    子类（如 ``GROUP_MESSAGE``）只匹配自身。
    """

    # ── 通配 ──
    ALL = "napcat.all"
    UNKNOWN = "napcat.unknown"

    # ── 元事件 ──
    META = "napcat.meta"
    LIFECYCLE_META = "napcat.meta.lifecycle"
    HEARTBEAT_META = "napcat.meta.heartbeat"

    # ── 消息事件 ──
    MESSAGE = "napcat.message"
    GROUP_MESSAGE = "napcat.message.group"
    PRIVATE_MESSAGE = "napcat.message.private"

    # ── 自身消息 ──
    SENT = "napcat.sent"
    GROUP_SENT = "napcat.sent.group"
    PRIVATE_SENT = "napcat.sent.private"

    # ── 请求事件 ──
    REQUEST = "napcat.request"
    FRIEND_REQUEST = "napcat.request.friend"
    GROUP_REQUEST = "napcat.request.group"

    # ── 通知事件 ──
    NOTICE = "napcat.notice"
    GROUP_UPLOAD_NOTICE = "napcat.notice.group_upload"
    GROUP_ADMIN_NOTICE = "napcat.notice.group_admin"
    GROUP_DECREASE_NOTICE = "napcat.notice.group_decrease"
    GROUP_INCREASE_NOTICE = "napcat.notice.group_increase"
    GROUP_BAN_NOTICE = "napcat.notice.group_ban"
    FRIEND_ADD_NOTICE = "napcat.notice.friend_add"
    GROUP_RECALL_NOTICE = "napcat.notice.group_recall"
    FRIEND_RECALL_NOTICE = "napcat.notice.friend_recall"
    GROUP_EMOJI_LIKE_NOTICE = "napcat.notice.group_msg_emoji_like"
    REACTION_NOTICE = "napcat.notice.reaction"
    GROUP_ESSENCE_NOTICE = "napcat.notice.essence"
    GROUP_CARD_NOTICE = "napcat.notice.group_card"

    # 三级分发：notice_type=notify → sub_type
    POKE_NOTIFY = "napcat.notice.poke"
    LUCKY_KING_NOTIFY = "napcat.notice.lucky_king"
    HONOR_NOTIFY = "napcat.notice.honor"

    @classmethod
    def get_specific_type(cls, message: dict[str, Any]) -> "NapcatType":
        """根据完整消息字典返回最具体的 NapcatType.

        读取 OneBot 协议中的 ``post_type`` 及对应二级/三级字段
        （``message_type``、``notice_type``、``request_type``、
        ``meta_event_type``、``sub_type``），
        路由到最具体的枚举成员。

        未知子类型回退到父类（如未知的 ``notice_type`` 返回 ``NOTICE``）。

        Args:
            message: 原始 OneBot 消息字典

        Returns:
            最具体的 NapcatType 枚举成员
        """
        post_type = message.get("post_type", "")

        if post_type == "meta_event":
            meta_type = message.get("meta_event_type", "")
            if meta_type == "lifecycle":
                return cls.LIFECYCLE_META
            elif meta_type == "heartbeat":
                return cls.HEARTBEAT_META
            return cls.META

        elif post_type == "message":
            msg_type = message.get("message_type", "")
            if msg_type == "private":
                return cls.PRIVATE_MESSAGE
            elif msg_type == "group":
                return cls.GROUP_MESSAGE
            return cls.MESSAGE

        elif post_type == "message_sent":
            msg_type = message.get("message_type", "")
            if msg_type == "private":
                return cls.PRIVATE_SENT
            elif msg_type == "group":
                return cls.GROUP_SENT
            return cls.SENT

        elif post_type == "request":
            req_type = message.get("request_type", "")
            if req_type == "friend":
                return cls.FRIEND_REQUEST
            elif req_type == "group":
                return cls.GROUP_REQUEST
            return cls.REQUEST

        elif post_type == "notice":
            notice_type = message.get("notice_type", "")

            # 三级分发：notice_type=notify → sub_type
            if notice_type == "notify":
                sub_type = message.get("sub_type", "")
                if sub_type == "poke":
                    return cls.POKE_NOTIFY
                elif sub_type == "lucky_king":
                    return cls.LUCKY_KING_NOTIFY
                elif sub_type == "honor":
                    return cls.HONOR_NOTIFY
                return cls.NOTICE

            _NOTICE_MAP = {
                "group_upload": cls.GROUP_UPLOAD_NOTICE,
                "group_admin": cls.GROUP_ADMIN_NOTICE,
                "group_decrease": cls.GROUP_DECREASE_NOTICE,
                "group_increase": cls.GROUP_INCREASE_NOTICE,
                "group_ban": cls.GROUP_BAN_NOTICE,
                "friend_add": cls.FRIEND_ADD_NOTICE,
                "group_recall": cls.GROUP_RECALL_NOTICE,
                "friend_recall": cls.FRIEND_RECALL_NOTICE,
                "group_msg_emoji_like": cls.GROUP_EMOJI_LIKE_NOTICE,
                "reaction": cls.REACTION_NOTICE,
                "essence": cls.GROUP_ESSENCE_NOTICE,
                "group_card": cls.GROUP_CARD_NOTICE,
            }
            return _NOTICE_MAP.get(notice_type, cls.NOTICE)

        return cls.UNKNOWN
