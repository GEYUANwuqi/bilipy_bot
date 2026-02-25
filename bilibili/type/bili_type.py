from base_cls import BaseType


class DynamicType(BaseType):
    """动态状态枚举."""
    ALL = "dynamic.all"  # 表示所有状态，用作通配符
    NEW = "dynamic.new"  # 新动态
    DELETED = "dynamic.deleted"  # 删除的动态
    NULL = "dynamic.null"  # 无变化


class LiveType(BaseType):
    """直播状态枚举."""
    ALL = "live.all"  # 表示所有状态，用作通配符
    ONLINE = "live.online"  # 在线
    OFFLINE = "live.offline"  # 离线
    OPEN = "live.open"  # 开播
    CLOSE = "live.close"  # 下播


class DanmakuType(BaseType):
    """弹幕状态枚举."""
    ALL = "danmaku.all"  # 表示所有状态，用作通配符
    DANMAKU = "danmaku.msg"  # 新弹幕
    GIFT = "danmaku.gift"  # 删除的弹幕
    OPEN = "danmaku.live_open"  # 开播
    OFFLINE = "danmaku.offline"  # 下播
