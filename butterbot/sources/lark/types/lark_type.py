"""ButterBot 飞书事件的层级状态枚举。"""

from butterbot.core.types import BaseType


class LarkType(BaseType):
    """飞书事件类型层级。"""

    ALL = "lark.all"
    UNKNOWN = "lark.unknown"

    MESSAGE = "lark.message"
    MESSAGE_RECEIVE = "lark.message.receive"
    MESSAGE_READ = "lark.message.read"
    MESSAGE_RECALLED = "lark.message.recalled"

    REACTION = "lark.reaction"
    REACTION_CREATED = "lark.reaction.created"
    REACTION_DELETED = "lark.reaction.deleted"

    CHAT = "lark.chat"
    CHAT_UPDATED = "lark.chat.updated"
    CHAT_DISBANDED = "lark.chat.disbanded"
    BOT_P2P_CHAT_ENTERED = "lark.chat.bot_p2p_entered"

    MEMBER = "lark.member"
    USER_ADDED = "lark.member.user.added"
    USER_DELETED = "lark.member.user.deleted"
    USER_WITHDRAWN = "lark.member.user.withdrawn"
    BOT_ADDED = "lark.member.bot.added"
    BOT_DELETED = "lark.member.bot.deleted"

    MENU = "lark.menu"
