"""Tests for BaseType enum matching logic."""

from bilipy_bot.core.types import BaseType


class TestType(BaseType):
    ALL = "test.all"
    ACTIVE = "test.active"
    INACTIVE = "test.inactive"


class OtherType(BaseType):
    ALL = "other.all"
    ON = "other.on"


class TestBaseType:
    """Test scope, state, and matches semantics."""

    def test_scope(self):
        """scope 属性返回第一个 '.' 前的部分."""
        assert TestType.ALL.scope == "test"
        assert TestType.ACTIVE.scope == "test"

    def test_state(self):
        """state 属性返回第一个 '.' 后的部分."""
        assert TestType.ALL.state == "all"
        assert TestType.ACTIVE.state == "active"

    def test_scope_and_state_nested(self):
        """值中包含多个 '.' 时，scope 取第一部分，state 取剩余部分."""

        class NestedType(BaseType):
            VALUE = "a.b.c"

        assert NestedType.VALUE.scope == "a"
        assert NestedType.VALUE.state == "b.c"

    def test_matches_same_type_scope_state(self):
        """同类、同域、同状态应匹配."""
        assert TestType.ACTIVE.matches(TestType.ACTIVE)

    def test_matches_wildcard_state(self):
        """state='all' 应匹配同类型同域下的任何状态."""
        assert TestType.ACTIVE.matches(TestType.ALL)
        assert TestType.INACTIVE.matches(TestType.ALL)

    def test_matches_wildcard_matches_self(self):
        """ALL 匹配自身."""
        assert TestType.ALL.matches(TestType.ALL)

    def test_matches_different_type(self):
        """不同类型应不匹配."""
        assert not TestType.ACTIVE.matches(OtherType.ON)  # noqa

    def test_matches_different_scope(self):
        """同类型但不同域应不匹配."""

        class AnotherScope(BaseType):
            ALL = "other.all"
            ACTIVE = "other.active"

        assert not TestType.ACTIVE.matches(AnotherScope.ACTIVE)

    def test_matches_different_state(self):
        """同类型同域但状态不同且非通配应不匹配."""
        assert not TestType.ACTIVE.matches(TestType.INACTIVE)

    def test_matches_all_against_any(self):
        """ALL 可匹配同类型同域下任意的具体状态."""

        class Varied(BaseType):
            ALL = "x.all"
            A = "x.a"
            B = "x.b"

        assert Varied.A.matches(Varied.ALL)
        assert Varied.B.matches(Varied.ALL)
