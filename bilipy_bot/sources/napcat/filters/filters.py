"""Napcat 预置过滤器.

提供一组可直接组合使用的 ``BaseFilter`` 子类：

- ``GroupFilter`` — 按群号过滤
- ``UserFilter`` — 按用户 ID 过滤
- ``SenderRoleFilter`` — 按发送者角色过滤（owner / admin / member）
- ``TextFilter`` — 按消息文本关键词过滤
- ``CommandFilter`` — 按完整命令精确匹配
- ``PrefixFilter`` — 按消息前缀匹配

所有过滤器遵循"安全"原则：事件不包含目标字段时默认拦截，
确保只处理明确匹配的事件类型。
"""

from logging import getLogger
from typing import TYPE_CHECKING, Literal

from bilipy_bot.core.filter import BaseFilter

if TYPE_CHECKING:
    from bilipy_bot.core.event import Event

_log = getLogger(__name__)


class GroupFilter(BaseFilter):
    """仅允许指定群组的事件通过。

    对不包含 ``group_id`` 字段的事件类型（如私聊、元事件），默认拦截。

    Usage:
        ``GroupFilter(123456)`` — 仅 group_id=123456 的事件
        ``GroupFilter(123456, 789012)`` — group_id 为 123456 **或** 789012 的事件
    """

    def __init__(self, *group_ids: int) -> None:
        self.filters = list(group_ids)

    def check(self, event: "Event") -> bool:
        group_id = getattr(event.data, "group_id", None)
        if group_id is None:
            return False  # 非群聊事件，安全拦截
        result = group_id in self.filters
        if not result:
            _log.debug("事件 %s 被 GroupFilter 拦截: group_id=%s", event.id, group_id)
        return result


class UserFilter(BaseFilter):
    """仅允许指定用户的事件通过。

    对不包含 ``user_id`` 字段的事件类型，默认拦截。

    Usage:
        ``UserFilter(10001)`` — 仅 user_id=10001 的事件
        ``UserFilter(10001, 10002)`` — user_id 为 10001 **或** 10002 的事件
    """

    def __init__(self, *user_ids: int) -> None:
        self.filters = list(user_ids)

    def check(self, event: "Event") -> bool:
        user_id = getattr(event.data, "user_id", None)
        if user_id is None:
            return False
        result = user_id in self.filters
        if not result:
            _log.debug("事件 %s 被 UserFilter 拦截: user_id=%s", event.id, user_id)
        return result


class SenderRoleFilter(BaseFilter):
    """仅允许指定发送者角色的群消息通过。

    通过 ``group_id`` 字段的存在判断是否为群聊事件，
    确认后检查 ``sender.role`` 的值。

    非群聊事件或缺少必要字段时默认拦截。

    Usage:
        ``SenderRoleFilter("owner", "admin")`` — 仅群主或管理员消息
    """

    def __init__(self, *roles: Literal["owner", "admin", "member"]) -> None:
        self.filters = list(roles)

    def check(self, event: "Event") -> bool:
        data = event.data
        # 通过 group_id 判断是否为群聊事件
        if getattr(data, "group_id", None) is None:
            return False
        sender = getattr(data, "sender", None)
        if sender is None:
            return False
        role = getattr(sender, "role", None)
        if role is None:
            return False
        result = role in self.filters
        if not result:
            _log.debug("事件 %s 被 SenderRoleFilter 拦截: role=%s", event.id, role)
        return result


class TextFilter(BaseFilter):
    """仅允许消息文本包含指定关键词的事件通过。

    非消息事件（通知、请求等）默认拦截。

    Args:
        *keywords: 关键词列表，任一匹配即通过
        case_sensitive: 是否大小写敏感，默认 ``False``

    Usage:
        ``TextFilter("help")`` — 消息包含 "help"（大小写不敏感）
        ``TextFilter("hello", case_sensitive=True)`` — 消息包含 "hello"（精确大小写）
    """

    def __init__(self, *keywords: str, case_sensitive: bool = False) -> None:
        self.filters = list(keywords)
        self._case_sensitive = case_sensitive

    def check(self, event: "Event") -> bool:
        data = event.data
        message = getattr(data, "message", None)
        if message is None:
            return False  # 非消息事件，安全拦截

        text = getattr(message, "plain_text", "")
        if not self._case_sensitive:
            text_lower = text.lower()
            return any(k.lower() in text_lower for k in self.filters)

        return any(k in text for k in self.filters)


class CommandFilter(BaseFilter):
    """仅允许消息以指定**完整命令**开头的事件通过。

    使用 ``text.split()[0]`` 提取命令部分进行精确匹配。
    适用于路由如 ``/help``、``/ban`` 等 bot 命令。

    非消息事件默认拦截。

    Usage:
        ``CommandFilter("/help")`` — 匹配 ``/help`` 和 ``/help args``，**不**匹配 ``/helpme``
        ``CommandFilter("/help", "/status")`` — 匹配 ``/help`` **或** ``/status``

    See Also:
        ``PrefixFilter`` — 如需按前缀（如所有 ``/`` 开头的消息）匹配
    """

    def __init__(self, *commands: str) -> None:
        self.filters = list(commands)

    def check(self, event: "Event") -> bool:
        data = event.data
        message = getattr(data, "message", None)
        if message is None:
            return False  # 非消息事件，安全拦截

        text = getattr(message, "plain_text", "")
        # 先取列表再判空：`"   ".split(maxsplit=1)` 返回 []，
        # 直接 [0] 会在纯空白消息上抛 IndexError，导致回调 task 异常、事件被吞。
        parts = text.split(maxsplit=1)
        command = parts[0] if parts else ""
        result = command in self.filters
        if not result:
            _log.debug("事件 %s 被 CommandFilter 拦截: command=%s", event.id, command)
        return result


class PrefixFilter(BaseFilter):
    """仅允许消息以指定前缀开头的事件通过。

    适合需要捕获所有以某字符开头的消息的场景，
    如所有 ``/`` 开头的 bot 命令。

    非消息事件默认拦截。

    Usage:
        ``PrefixFilter("/")`` — 匹配任何 ``/`` 开头的消息
        ``PrefixFilter("!", ".")`` — 匹配 ``!`` **或** ``.`` 开头的消息

    See Also:
        ``CommandFilter`` — 如需精确匹配完整命令
    """

    def __init__(self, *prefixes: str) -> None:
        self.filters = list(prefixes)

    def check(self, event: "Event") -> bool:
        data = event.data
        message = getattr(data, "message", None)
        if message is None:
            return False  # 非消息事件，安全拦截

        text = getattr(message, "plain_text", "")
        result = any(text.startswith(prefix) for prefix in self.filters)
        if not result:
            _log.debug("事件 %s 被 PrefixFilter 拦截: text=%s", event.id, text)
        return result
