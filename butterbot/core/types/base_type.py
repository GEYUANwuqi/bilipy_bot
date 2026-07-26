import re
from enum import Enum
from typing import TypeVar, Union

_BaseTypeSelf = Union[str, re.Pattern[str], "BaseType"]


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

    def matches(self, rule: _BaseTypeSelf) -> bool:
        """判断状态是否匹配.

        支持三种匹配方式：

        - ``BaseType``: 按枚举类型匹配（需同 type、同 scope）
          - state 为 "all" 时通配同 scope 下所有状态
          - 支持层级匹配：父状态匹配子状态（如 "message" 匹配 "message.group"）
        - ``str``: 作为正则表达式，用 ``re.fullmatch`` 与 ``self.value`` 匹配
        - ``re.Pattern[str]``: 编译好的正则对象，直接调用其 ``fullmatch`` 方法

        Args:
            rule: 状态过滤器（``BaseType`` 枚举，``str`` 正则，或编译好的 ``re.Pattern``）

        Returns:
            bool: 匹配结果
        """
        if isinstance(rule, BaseType):
            # 枚举匹配：需同 type、同 scope；state="all" 通配；层级父匹配子
            if type(self) is type(rule):
                if self.scope == rule.scope:
                    if (
                        self.state == rule.state
                        or rule.state == "all"
                        or self.state.startswith(rule.state + ".")
                    ):
                        return True
                    return False
                return False
            return False

        if isinstance(rule, re.Pattern):
            return bool(rule.fullmatch(self.value))

        # str 正则匹配：直接与 self.value 全量匹配
        return bool(re.fullmatch(rule, self.value))

    @classmethod
    def matching_statuses(cls, rule: _BaseTypeSelf) -> list["BaseType"]:
        """返回当前枚举类中所有匹配给定规则的成员.

        遍历当前枚举类的所有成员，筛掉通配标签（state="all"），
        返回余下成员中能通过 ``matches(rule)`` 的元素列表。

        Args:
            rule: 状态过滤器（``BaseType`` 枚举、``str`` 或 ``re.Pattern`` 正则）

        Returns:
            匹配的枚举成员列表（不含 state="all" 的通配成员）
        """
        return [m for m in cls if m.state != "all" and m.matches(rule)]


BaseTypeT = TypeVar("BaseTypeT", bound=BaseType)
