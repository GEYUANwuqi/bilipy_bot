from enum import StrEnum
from typing import TypeVar


class BaseType(StrEnum):
    """标签枚举基类，提供通用的匹配方法."""

    def matches(self, other: "BaseType") -> bool:
        """判断状态是否匹配.

        Args:
            other: 要匹配的标签

        Returns:
            bool: 如果 self 或 other 的值是 "all"，或者两者相等，返回 True
        """
        return self.value == "all" or other.value == "all" or self == other


class DynamicType(BaseType):
    """动态状态枚举."""
    ALL = "all"  # 表示所有状态，用作通配符
    NEW = "new" # 新动态
    DELETED = "deleted" # 删除的动态
    NULL = "null" # 无变化


class LiveType(BaseType):
    """直播状态枚举."""
    ALL = "all"  # 表示所有状态，用作通配符
    ONLINE = "online" # 在线
    OFFLINE = "offline" # 离线
    OPEN = "open" # 开播
    CLOSE = "close" # 下播

BaseTypeT = TypeVar("BaseTypeT", bound=BaseType)
