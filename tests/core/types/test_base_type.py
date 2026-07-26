"""Tests for BaseType enum matching logic."""

import re

from butterbot.core.types import BaseType


class SampleType(BaseType):
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
        assert SampleType.ALL.scope == "test"
        assert SampleType.ACTIVE.scope == "test"

    def test_state(self):
        """state 属性返回第一个 '.' 后的部分."""
        assert SampleType.ALL.state == "all"
        assert SampleType.ACTIVE.state == "active"

    def test_scope_and_state_nested(self):
        """值中包含多个 '.' 时，scope 取第一部分，state 取剩余部分."""

        class NestedType(BaseType):
            VALUE = "a.b.c"

        assert NestedType.VALUE.scope == "a"
        assert NestedType.VALUE.state == "b.c"

    def test_matches_same_type_scope_state(self):
        """同类、同域、同状态应匹配."""
        assert SampleType.ACTIVE.matches(SampleType.ACTIVE)

    def test_matches_wildcard_state(self):
        """state='all' 应匹配同类型同域下的任何状态."""
        assert SampleType.ACTIVE.matches(SampleType.ALL)
        assert SampleType.INACTIVE.matches(SampleType.ALL)

    def test_matches_wildcard_matches_self(self):
        """ALL 匹配自身."""
        assert SampleType.ALL.matches(SampleType.ALL)

    def test_matches_different_type(self):
        """不同类型应不匹配."""
        assert not SampleType.ACTIVE.matches(OtherType.ON)  # noqa

    def test_matches_different_scope(self):
        """同类型但不同域应不匹配."""

        class AnotherScope(BaseType):
            ALL = "other.all"
            ACTIVE = "other.active"

        assert not SampleType.ACTIVE.matches(AnotherScope.ACTIVE)

    def test_matches_different_state(self):
        """同类型同域但状态不同且非通配应不匹配."""
        assert not SampleType.ACTIVE.matches(SampleType.INACTIVE)

    def test_matches_all_against_any(self):
        """ALL 可匹配同类型同域下任意的具体状态."""

        class Varied(BaseType):
            ALL = "x.all"
            A = "x.a"
            B = "x.b"

        assert Varied.A.matches(Varied.ALL)
        assert Varied.B.matches(Varied.ALL)

    # ============ str 正则匹配 ============

    def test_matches_str_regex_exact(self):
        """str 正则精确匹配枚举值."""
        assert SampleType.ACTIVE.matches("test.active")

    def test_matches_str_regex_wildcard(self):
        """str 正则 ``.*`` 通配应匹配."""
        assert SampleType.ACTIVE.matches(r"test\..*")
        assert SampleType.INACTIVE.matches(r"test\..*")

    def test_matches_str_regex_group(self):
        """str 正则字符组应正确匹配."""
        assert SampleType.ACTIVE.matches(r"test\.(active|inactive)")
        assert SampleType.INACTIVE.matches(r"test\.(active|inactive)")

    def test_matches_str_regex_no_match(self):
        """不匹配的 str 正则应返回 False."""
        assert not SampleType.ACTIVE.matches(r"test\.inactive")
        assert not SampleType.ACTIVE.matches(r"other\..*")

    def test_matches_str_regex_scope_pattern(self):
        """str 正则匹配 scope 维度."""

        class ScopeType(BaseType):
            A = "scope_a.event"
            B = "scope_b.event"

        assert ScopeType.A.matches(r"scope_a\..*")
        assert not ScopeType.B.matches(r"scope_a\..*")

    def test_matches_str_regex_fullmatch_enforced(self):
        """re.fullmatch 行为：正则必须完全匹配整个值，不能只匹配前缀."""
        assert SampleType.ACTIVE.matches(r"test\.active")
        assert not SampleType.ACTIVE.matches(r"test\.")  # 不完整，fullmatch 失败

    # ============ re.Pattern[str] 匹配 ============

    def test_matches_pattern_exact(self):
        """编译好的 Pattern 精确匹配枚举值."""
        pattern = re.compile(r"test\.active")
        assert SampleType.ACTIVE.matches(pattern)

    def test_matches_pattern_wildcard(self):
        """编译好的 Pattern 通配匹配."""
        pattern = re.compile(r"test\..*")
        assert SampleType.ACTIVE.matches(pattern)
        assert SampleType.INACTIVE.matches(pattern)

    def test_matches_pattern_no_match(self):
        """不匹配的 Pattern 应返回 False."""
        pattern = re.compile(r"test\.inactive")
        assert not SampleType.ACTIVE.matches(pattern)

    def test_matches_pattern_fullmatch_enforced(self):
        """Pattern.fullmatch 行为：必须完全匹配，不能只匹配前缀."""
        pattern = re.compile(r"test\.")
        assert not SampleType.ACTIVE.matches(pattern)


class NestedType(BaseType):
    ALL = "nested.all"
    PARENT = "nested.parent"
    CHILD_A = "nested.parent.child_a"
    CHILD_B = "nested.parent.child_b"
    SIBLING = "nested.other"


class TestHierarchicalMatching:
    """层级匹配：父状态匹配子状态."""

    def test_parent_matches_child(self):
        """父状态应匹配子状态（前缀匹配）."""
        assert NestedType.CHILD_A.matches(NestedType.PARENT)

    def test_child_does_not_match_parent(self):
        """子状态不应反向匹配父状态（单向）."""
        assert not NestedType.PARENT.matches(NestedType.CHILD_A)

    def test_all_still_matches_all(self):
        """ALL 仍通配同 scope 下所有状态."""
        assert NestedType.CHILD_A.matches(NestedType.ALL)
        assert NestedType.PARENT.matches(NestedType.ALL)

    def test_sibling_does_not_match(self):
        """不同父节点的同级状态不应匹配."""
        assert not NestedType.CHILD_A.matches(NestedType.SIBLING)
        assert not NestedType.SIBLING.matches(NestedType.PARENT)

    def test_exact_match_still_works(self):
        """完全相同状态仍匹配."""
        assert NestedType.CHILD_A.matches(NestedType.CHILD_A)

    def test_different_scope_no_match(self):
        """不同 scope 即使是前缀也不匹配."""

        class ScopeB(BaseType):
            PARENT = "scope_b.parent"
            CHILD = "scope_b.parent.child"

        assert not NestedType.CHILD_A.matches(ScopeB.PARENT)

    def test_prefix_boundary_respects_dot(self):
        """前缀匹配必须到`.`边界，避免部分段误匹配."""

        class BoundaryType(BaseType):
            PARTIAL = "test.parent.c"
            CHILD = "test.parent.child"

        assert not BoundaryType.CHILD.matches(BoundaryType.PARTIAL)


class TestMatchingStatuses:
    """测试 matching_statuses 类方法."""

    def test_base_type_rule_exact(self):
        """BaseType 规则应匹配对应的具体成员."""
        result = SampleType.matching_statuses(SampleType.ACTIVE)
        assert SampleType.ACTIVE in result
        assert SampleType.INACTIVE not in result

    def test_base_type_rule_wildcard(self):
        """ALL 规则应匹配所有具体成员（排除 ALL 自身）."""
        result = SampleType.matching_statuses(SampleType.ALL)
        assert SampleType.ACTIVE in result
        assert SampleType.INACTIVE in result
        assert SampleType.ALL not in result  # ALL 被排除

    def test_str_regex_rule(self):
        """str 正则应展开到所有匹配的具体成员."""
        result = SampleType.matching_statuses(r"test\.(active|inactive)")
        assert SampleType.ACTIVE in result
        assert SampleType.INACTIVE in result

    def test_str_regex_no_match(self):
        """不匹配的 str 正则应返回空列表."""
        result = SampleType.matching_statuses(r"test\.nonexistent")
        assert result == []

    def test_pattern_rule(self):
        """re.Pattern 应展开到所有匹配的具体成员."""
        pattern = re.compile(r"test\.active")
        result = SampleType.matching_statuses(pattern)
        assert SampleType.ACTIVE in result
        assert SampleType.INACTIVE not in result

    def test_excludes_wildcard_member(self):
        """state='all' 的成员不应出现在结果中."""
        result = SampleType.matching_statuses(SampleType.ALL)
        assert SampleType.ALL not in result

    def test_cross_type_returns_empty(self):
        """不同类型之间不应有匹配."""

        class OtherType(BaseType):
            ALL = "other.all"
            VALUE = "other.value"

        result = SampleType.matching_statuses(OtherType.VALUE)
        assert result == []

    def test_hierarchical_matching(self):
        """层级父状态展开时应匹配所有子状态."""

        class HierType(BaseType):
            ALL = "hier.all"
            PARENT = "hier.parent"
            CHILD_A = "hier.parent.a"
            CHILD_B = "hier.parent.b"

        result = HierType.matching_statuses(HierType.PARENT)
        assert HierType.PARENT in result  # 自身
        assert HierType.CHILD_A in result  # 子状态
        assert HierType.CHILD_B in result  # 子状态
