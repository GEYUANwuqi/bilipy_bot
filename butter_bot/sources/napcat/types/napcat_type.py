from butter_bot.core.types import BaseType


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
