"""Tests for BaseDataMixin repr formatting."""

from butter_bot.core.data import BaseDataMixin


class SimpleData(BaseDataMixin):
    """Simple data class with public and private attrs."""

    _repr_exclude = {"internal"}


class TestBaseDataMixin:
    """Test BaseDataMixin.__repr__ and __str__."""

    def test_repr_shows_public_attrs(self):
        """__repr__ 应包含公有属性."""
        d = SimpleData()
        d.name = "test"  # type: ignore[attr-defined]
        d.value = 42  # type: ignore[attr-defined]
        r = repr(d)
        assert "name=" in r
        assert "value=" in r

    def test_repr_excludes_private_attrs(self):
        """__repr__ 应排除下划线开头的属性."""
        d = SimpleData()
        d._secret = "hidden"  # type: ignore[attr-defined]
        r = repr(d)
        assert "secret" not in r

    def test_repr_excludes_marked_attrs(self):
        """__repr__ 应排除 _repr_exclude 集合中的属性."""
        d = SimpleData()
        d.internal = "should_not_appear"  # type: ignore[attr-defined]
        d.public = "visible"  # type: ignore[attr-defined]
        r = repr(d)
        assert "internal" not in r
        assert "public" in r

    def test_str_delegates_to_repr(self):
        """__str__ 应返回与 __repr__ 相同的结果."""
        d = SimpleData()
        d.name = "test"  # type: ignore[attr-defined]
        assert str(d) == repr(d)
