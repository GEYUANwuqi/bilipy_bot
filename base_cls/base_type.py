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


BaseTypeT = TypeVar("BaseTypeT", bound=BaseType)
