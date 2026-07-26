"""Tests for BaseFilter, AndFilter, OrFilter."""

from butter_bot.core.data import BaseDataMixin
from butter_bot.core.event import Event
from butter_bot.core.filter import AndFilter, BaseFilter, OrFilter
from butter_bot.core.types import BaseType


class NullData(BaseDataMixin):
    """Minimal data object for filter tests."""


def _null_event(status: BaseType) -> Event:
    """Create a minimal Event for filter tests."""
    return Event(data=NullData(), status=status)


class MockFilter(BaseFilter):
    """A filter that returns a predetermined result."""

    def __init__(self, should_pass: bool = True, label: str = ""):
        self._should_pass = should_pass
        self.filters = [self]
        self._label = label

    def check(self, event: "Event") -> bool:
        return self._should_pass


class MockType(BaseType):
    ALL = "mock.all"


class TestAndFilter:
    """Test AndFilter logic."""

    def test_all_pass(self):
        """所有子过滤器通过时应返回 True."""
        f = AndFilter(MockFilter(True), MockFilter(True))
        assert f.check(_null_event(MockType.ALL))

    def test_one_fails(self):
        """任一子过滤器不通过时应返回 False."""
        f = AndFilter(MockFilter(True), MockFilter(False), MockFilter(True))
        assert not f.check(_null_event(MockType.ALL))

    def test_all_fail(self):
        """所有子过滤器不通过时应返回 False."""
        f = AndFilter(MockFilter(False), MockFilter(False))
        assert not f.check(_null_event(MockType.ALL))

    def test_empty_filters(self):
        """AndFilter 无过滤器时（空真）应返回 True."""
        f = AndFilter()
        assert f.check(_null_event(MockType.ALL))

    def test_repr(self):
        """__repr__ 应包含类名和 filters."""
        f = AndFilter(MockFilter(True))
        r = repr(f)
        assert "AndFilter" in r
        assert "filters" in r


class TestOrFilter:
    """Test OrFilter logic."""

    def test_all_pass(self):
        """所有子过滤器通过时应返回 True."""
        f = OrFilter(MockFilter(True), MockFilter(True))
        assert f.check(_null_event(MockType.ALL))

    def test_one_passes(self):
        """任一子过滤器通过时应返回 True."""
        f = OrFilter(MockFilter(False), MockFilter(True), MockFilter(False))
        assert f.check(_null_event(MockType.ALL))

    def test_all_fail(self):
        """所有子过滤器不通过时应返回 False."""
        f = OrFilter(MockFilter(False), MockFilter(False))
        assert not f.check(_null_event(MockType.ALL))

    def test_empty_filters(self):
        """OrFilter 无过滤器时（空假）应返回 False."""
        f = OrFilter()
        assert not f.check(_null_event(MockType.ALL))

    def test_repr(self):
        """__repr__ 应包含类名和 filters."""
        f = OrFilter(MockFilter(True))
        r = repr(f)
        assert "OrFilter" in r
        assert "filters" in r


class TestOperators:
    """Test & and | operator chaining."""

    def test_and_operator(self):
        """f1 & f2 应产生 AndFilter."""
        f1 = MockFilter(True)
        f2 = MockFilter(True)
        combined = f1 & f2
        assert isinstance(combined, AndFilter)

    def test_or_operator(self):
        """f1 | f2 应产生 OrFilter."""
        f1 = MockFilter(True)
        f2 = MockFilter(True)
        combined = f1 | f2
        assert isinstance(combined, OrFilter)

    def test_chained_operators(self):
        """(f1 & f2) | f3 应产生正确结构的过滤器."""
        f1 = MockFilter(True)
        f2 = MockFilter(True)
        f3 = MockFilter(False)
        combined = (f1 & f2) | f3
        assert isinstance(combined, OrFilter)
        assert len(combined.filters) == 2
        assert isinstance(combined.filters[0], AndFilter)

    def test_and_operator_evaluation(self):
        """& 组合的过滤器应正确求值."""
        f = MockFilter(True) & MockFilter(True) & MockFilter(False)
        assert not f.check(_null_event(MockType.ALL))

    def test_or_operator_evaluation(self):
        """| 组合的过滤器应正确求值."""
        f = MockFilter(False) | MockFilter(False) | MockFilter(True)
        assert f.check(_null_event(MockType.ALL))
