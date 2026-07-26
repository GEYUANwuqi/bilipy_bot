"""Tests for Event dataclass."""

import dataclasses

from butter_bot.core.data import BaseDataMixin
from butter_bot.core.event import Event
from butter_bot.core.types import BaseType


class EmptyData(BaseDataMixin):
    """Minimal data class for testing."""


class TestEvent:
    """Test Event construction, identity, and repr."""

    def test_construction(self):
        """Event 应正确设置 data, status, id 字段."""
        data = EmptyData()
        status = _event_type("test.a")
        event = Event(data=data, status=status)
        assert event.data is data
        assert event.status is status
        assert event.id is not None

    def test_id_is_unique(self):
        """连续创建的两个 Event 应具有不同 id."""
        status_a = _event_type("test.a")
        status_b = _event_type("test.b")
        e1 = Event(data=EmptyData(), status=status_a)
        e2 = Event(data=EmptyData(), status=status_b)
        assert e1.id != e2.id

    def test_id_deterministic_when_provided(self):
        """传入 id 参数时应使用该值."""
        event = Event(data=EmptyData(), status=_event_type("test.a"), id="my-id")
        assert event.id == "my-id"

    def test_is_dataclass(self):
        """Event 应被 dataclasses 识别."""
        assert dataclasses.is_dataclass(Event)

    def test_repr(self):
        """__repr__ 应包含 data 和 status."""
        data = EmptyData()
        status = _event_type("test.a")
        event = Event(data=data, status=status)
        r = repr(event)
        assert "data=" in r
        assert "status=" in r

    def test_str(self):
        """__str__ 应与 __repr__ 一致."""
        event = Event(data=EmptyData(), status=_event_type("test.a"))
        assert str(event) == repr(event)


def _event_type(value: str) -> BaseType:
    """Create a temporary BaseType value with the given string."""

    class Tmp(BaseType):
        V = value

    return Tmp.V  # type: ignore  # pyright: BaseType match from Enum member is valid at runtime
