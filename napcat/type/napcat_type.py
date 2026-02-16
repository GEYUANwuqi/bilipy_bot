from base_cls import BaseType


class NapcatType(BaseType):
    """napcat状态枚举."""
    ALL = "napcat.all"  # 表示所有状态，用作通配符
    META = "napcat.meta"  # 元信息
    MESSAGE = "napcat.message"  # 群/私聊消息
    REQUEST = "napcat.request"  # 请求消息
    NOTICE = "napcat.notice"  # 通知消息
    SENT = "napcat.sent"  # 自身消息
    UNKNOWN = "napcat.unknown"  # 未知消息

    @classmethod
    def get_type(cls, post_type: str) -> "NapcatType":
        """返回 NapcatType 枚举实例.
        Args:
            post_type: post_type
        """
        if post_type == "meta_event":
            return NapcatType.META
        elif post_type == "message":
            return NapcatType.MESSAGE
        elif post_type == "request":
            return NapcatType.REQUEST
        elif post_type == "notice":
            return NapcatType.NOTICE
        elif post_type == "message_sent":
            return NapcatType.SENT
        else:
            return NapcatType.UNKNOWN
