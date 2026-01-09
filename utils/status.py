from enum import Enum
from typing import TypeVar


class BaseType(str, Enum):
    """标签枚举基类，提供通用的匹配方法."""

    @property
    def scope(self) -> str:
        """返回标签的作用域."""
        return self.value.split(".", 1)[0]

    @property
    def state(self) -> str:
        """返回标签的状态."""
        return self.value.split(".", 1)[1]

    def matches(self, rule: "BaseType") -> bool:
        """判断状态是否匹配.

        Args:
            rule: 要匹配的标签

        Returns:
            bool: 在作用域相同且具体状态相同或rule为通配符时返回True，否则返回False
        """
        if self.scope == rule.scope:  # 作用域
            if self.state == rule.state:  # 具体状态
                return True
            elif rule.state == "all":  # 通配符
                return True
            else:
                return False
        else:
            return False


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
    NEW = "danmaku.msg"  # 新弹幕
    GIFT = "danmaku.gift"  # 删除的弹幕
    LIVE = "danmaku.live"  # 开播
    OFFLINE = "danmaku.offline"  # 下播


BaseTypeT = TypeVar("BaseTypeT", bound=BaseType)
