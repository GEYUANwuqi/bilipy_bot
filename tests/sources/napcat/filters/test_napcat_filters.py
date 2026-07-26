"""Tests for Napcat pre-built filters."""

from dataclasses import dataclass, field

from bilipy_bot.core.data import BaseDataMixin
from bilipy_bot.core.event import Event
from bilipy_bot.core.filter import BaseFilter
from bilipy_bot.core.types import BaseType
from bilipy_bot.sources.napcat.filters import (
    CommandFilter,
    GroupFilter,
    PrefixFilter,
    SenderRoleFilter,
    TextFilter,
    UserFilter,
)

# ==================== 模拟数据类 ====================


@dataclass
class MockSender:
    """模拟群聊发送者."""

    user_id: int = 0
    nickname: str = ""
    role: str = "member"
    card: str = ""


@dataclass
class MockMessage:
    """模拟消息内容."""

    plain_text: str = ""


@dataclass
class MockGroupMessageData(BaseDataMixin):
    """模拟群聊消息事件数据."""

    group_id: int = 0
    user_id: int = 0
    sender: MockSender = field(default_factory=lambda: MockSender())
    message: MockMessage = field(default_factory=lambda: MockMessage())


@dataclass
class MockPrivateMessageData(BaseDataMixin):
    """模拟私聊消息事件数据."""

    user_id: int = 0
    message: MockMessage = field(default_factory=lambda: MockMessage())


@dataclass
class MockNoticeData(BaseDataMixin):
    """模拟通知事件数据（有 group_id/user_id，无 message/sender.role）."""

    group_id: int = 0
    user_id: int = 0
    notice_type: str = ""


@dataclass
class MockMetaData(BaseDataMixin):
    """模拟元事件数据（无 group_id/user_id/message/sender）."""

    sub_type: str = ""


# ==================== 测试用枚举 ====================


class MockNapcatType(BaseType):
    ALL = "mock.all"


# ==================== 辅助函数 ====================


def _make_group_msg(
    group_id: int = 0,
    user_id: int = 0,
    role: str = "member",
    text: str = "",
) -> Event:
    """创建一个模拟群聊消息事件."""
    sender = MockSender(user_id=user_id, role=role)
    message = MockMessage(plain_text=text)
    data = MockGroupMessageData(
        group_id=group_id, user_id=user_id, sender=sender, message=message
    )
    return Event(data=data, status=MockNapcatType.ALL)


def _make_private_msg(user_id: int = 0, text: str = "") -> Event:
    """创建一个模拟私聊消息事件."""
    message = MockMessage(plain_text=text)
    data = MockPrivateMessageData(user_id=user_id, message=message)
    return Event(data=data, status=MockNapcatType.ALL)


def _make_notice(group_id: int = 0, user_id: int = 0) -> Event:
    """创建一个模拟通知事件."""
    data = MockNoticeData(group_id=group_id, user_id=user_id)
    return Event(data=data, status=MockNapcatType.ALL)


def _make_meta() -> Event:
    """创建一个模拟元事件."""
    data = MockMetaData()
    return Event(data=data, status=MockNapcatType.ALL)


# ==================== GroupFilter 测试 ====================


class TestGroupFilter:
    def test_matching_group(self):
        """匹配 group_id 时应通过."""
        f = GroupFilter(100)
        assert f.check(_make_group_msg(group_id=100))

    def test_matching_multiple_groups(self):
        """group_id 在允许列表中的任一值即通过."""
        f = GroupFilter(100, 200)
        assert f.check(_make_group_msg(group_id=200))

    def test_non_matching_group(self):
        """不匹配 group_id 时应拦截."""
        f = GroupFilter(200)
        assert not f.check(_make_group_msg(group_id=100))

    def test_non_group_event_blocked(self):
        """无 group_id 的事件（如元事件）应被拦截（fail-closed）."""
        f = GroupFilter(100)
        assert not f.check(_make_meta())

    def test_private_message_blocked(self):
        """私聊消息无 group_id，应被拦截（fail-closed）."""
        f = GroupFilter(100)
        assert not f.check(_make_private_msg())


# ==================== UserFilter 测试 ====================


class TestUserFilter:
    def test_matching_user(self):
        """匹配 user_id 时应通过."""
        f = UserFilter(10001)
        assert f.check(_make_group_msg(user_id=10001))

    def test_matching_multiple_users(self):
        """user_id 在允许列表中的任一值即通过."""
        f = UserFilter(10001, 10002)
        assert f.check(_make_group_msg(user_id=10002))

    def test_non_matching_user(self):
        """不匹配 user_id 时应拦截."""
        f = UserFilter(20001)
        assert not f.check(_make_group_msg(user_id=10001))

    def test_no_user_id_event_blocked(self):
        """无 user_id 的事件（如元事件）应被拦截（fail-closed）."""
        f = UserFilter(10001)
        assert not f.check(_make_meta())


# ==================== SenderRoleFilter 测试 ====================


class TestSenderRoleFilter:
    def test_matching_owner(self):
        """发送者为 owner 时应通过."""
        f = SenderRoleFilter("owner")
        assert f.check(_make_group_msg(role="owner"))

    def test_matching_admin(self):
        """发送者为 admin 时应通过."""
        f = SenderRoleFilter("admin")
        assert f.check(_make_group_msg(role="admin"))

    def test_matching_member(self):
        """发送者为 member 时应通过."""
        f = SenderRoleFilter("member")
        assert f.check(_make_group_msg(role="member"))

    def test_multiple_roles(self):
        """匹配多个角色中的任一即通过."""
        f = SenderRoleFilter("owner", "admin")
        assert f.check(_make_group_msg(role="admin"))
        assert not f.check(_make_group_msg(role="member"))

    def test_non_group_event_blocked(self):
        """非群聊事件（无 group_id）应被拦截（fail-closed）."""
        f = SenderRoleFilter("owner")
        assert not f.check(_make_meta())

    def test_private_message_blocked(self):
        """私聊消息（无 group_id/role）应被拦截（fail-closed）."""
        f = SenderRoleFilter("owner")
        assert not f.check(_make_private_msg())


# ==================== TextFilter 测试 ====================


class TestTextFilter:
    def test_keyword_found(self):
        """消息包含关键词时应通过."""
        f = TextFilter("hello")
        assert f.check(_make_group_msg(text="say hello world"))

    def test_keyword_not_found(self):
        """消息不包含关键词时应拦截."""
        f = TextFilter("hello")
        assert not f.check(_make_group_msg(text="goodbye world"))

    def test_case_insensitive_by_default(self):
        """默认大小写不敏感."""
        f = TextFilter("hello")
        assert f.check(_make_group_msg(text="Say Hello World"))

    def test_case_sensitive(self):
        """设置 case_sensitive=True 时区分大小写."""
        f = TextFilter("hello", case_sensitive=True)
        assert not f.check(_make_group_msg(text="Say Hello World"))

    def test_multiple_keywords(self):
        """匹配多个关键词中的任一即通过."""
        f = TextFilter("apple", "banana")
        assert f.check(_make_group_msg(text="I like banana"))
        assert not f.check(_make_group_msg(text="I like cherry"))

    def test_non_message_event_blocked(self):
        """非消息事件（无 message 字段）应被拦截（fail-closed）."""
        f = TextFilter("hello")
        assert not f.check(_make_notice())

    def test_private_message_found(self):
        """私聊消息同样支持文本过滤."""
        f = TextFilter("hello")
        assert f.check(_make_private_msg(text="say hello"))


# ==================== CommandFilter 测试 ====================


class TestCommandFilter:
    def test_exact_command_match(self):
        """完整命令匹配时应通过."""
        f = CommandFilter("/help")
        assert f.check(_make_group_msg(text="/help"))

    def test_command_with_args(self):
        """命令带参数时应匹配（text.split()[0] 命中）."""
        f = CommandFilter("/help")
        assert f.check(_make_group_msg(text="/help me please"))

    def test_reject_similar_prefix(self):
        """不匹配相似前缀的命令."""
        f = CommandFilter("/help")
        assert not f.check(_make_group_msg(text="/helpme"))

    def test_multiple_commands(self):
        """匹配多个命令中的任一即通过."""
        f = CommandFilter("/help", "/status")
        assert f.check(_make_group_msg(text="/status"))
        assert f.check(_make_group_msg(text="/help"))
        assert not f.check(_make_group_msg(text="/ban"))

    def test_non_message_event_blocked(self):
        """非消息事件应被拦截（fail-closed）."""
        f = CommandFilter("/help")
        assert not f.check(_make_notice())

    def test_empty_text(self):
        """空文本不应通过."""
        f = CommandFilter("/help")
        assert not f.check(_make_group_msg(text=""))


# ==================== PrefixFilter 测试 ====================


class TestPrefixFilter:
    def test_prefix_match(self):
        """前缀匹配时应通过."""
        f = PrefixFilter("/")
        assert f.check(_make_group_msg(text="/help"))

    def test_prefix_no_match(self):
        """前缀不匹配时应拦截."""
        f = PrefixFilter("/")
        assert not f.check(_make_group_msg(text="!help"))

    def test_multiple_prefixes(self):
        """匹配多个前缀中的任一即通过."""
        f = PrefixFilter("/", "!")
        assert f.check(_make_group_msg(text="!help"))
        assert f.check(_make_group_msg(text="/status"))
        assert not f.check(_make_group_msg(text=".help"))

    def test_non_message_event_blocked(self):
        """非消息事件应被拦截（fail-closed）."""
        f = PrefixFilter("/")
        assert not f.check(_make_notice())

    def test_prefix_vs_command_distinction(self):
        """确认 PrefixFilter 与 CommandFilter 的语义差异."""
        prefix_f = PrefixFilter("/")
        cmd_f = CommandFilter("/help")
        # /helpme 匹配 PrefixFilter("/") 但不匹配 CommandFilter("/help")
        event = _make_group_msg(text="/helpme")
        assert prefix_f.check(event)
        assert not cmd_f.check(event)


# ==================== 组合过滤器短路测试 ====================


class TestCombinedFilters:
    def test_and_filter_short_circuit(self):
        """AndFilter: 第一个 filter 返回 False 时，第二个不被调用."""
        calls: list[str] = []

        class TrackingFilter(BaseFilter):
            def __init__(self):
                self.filters = []

            def check(self, event):
                calls.append(event.id)
                return True

        f = GroupFilter(999) & TrackingFilter()  # GroupFilter 先拦截
        assert not f.check(_make_group_msg(group_id=100))
        assert calls == []

    def test_and_filter_both_pass(self):
        """AndFilter: 全部通过时返回 True."""
        f = GroupFilter(100) & TextFilter("hello")
        assert f.check(_make_group_msg(group_id=100, text="say hello"))

    def test_and_filter_one_fails(self):
        """AndFilter: 任一不通过时返回 False."""
        f = GroupFilter(100) & TextFilter("hello")
        assert not f.check(_make_group_msg(group_id=100, text="goodbye"))

    def test_or_filter_both_fail(self):
        """OrFilter: 全部不通过时返回 False."""
        f = GroupFilter(100) | GroupFilter(200)
        assert not f.check(_make_group_msg(group_id=300))

    def test_or_filter_one_passes(self):
        """OrFilter: 任一通过时返回 True."""
        f = GroupFilter(100) | GroupFilter(200)
        assert f.check(_make_group_msg(group_id=100))
        assert f.check(_make_group_msg(group_id=200))
