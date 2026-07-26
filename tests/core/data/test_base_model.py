"""Tests for BaseDataModel discriminator dispatch."""

from typing import ClassVar

import pytest

from butterbot.core.data import AutoDispatchList, BaseDataModel


class SampleRoot(BaseDataModel):
    discriminator_field: ClassVar[str] = "kind"
    name: str = ""


class SampleCat(SampleRoot):
    discriminator_value: ClassVar[str] = "cat"
    whiskers: int = 0


class SampleDog(SampleRoot):
    discriminator_value: ClassVar[str] = "dog"
    tail_length: float = 0.0


class TestBaseDataModel:
    """Test discriminator registration and dispatch."""

    def test_from_dict_dispatches_correctly(self):
        """from_dict 应分发到正确的子类."""
        cat = SampleRoot.from_dict({"kind": "cat", "name": "Kitty", "whiskers": 3})
        assert isinstance(cat, SampleCat)
        assert cat.name == "Kitty"
        assert cat.whiskers == 3

        dog = SampleRoot.from_dict({"kind": "dog", "name": "Buddy", "tail_length": 5.5})
        assert isinstance(dog, SampleDog)
        assert dog.name == "Buddy"
        assert dog.tail_length == 5.5

    def test_from_dict_missing_field_raises(self):
        """缺少 discriminator_field 应抛出 ValueError."""
        with pytest.raises(ValueError, match="Missing discriminator"):
            SampleRoot.from_dict({"name": "Unknown"})

    def test_from_dict_unknown_value_raises(self):
        """未知的 discriminator_value 应抛出 ValueError."""
        with pytest.raises(ValueError, match="Unknown type"):
            SampleRoot.from_dict({"kind": "bird", "name": "Tweety"})

    def test_from_dict_no_discriminator(self):
        """没有 discriminator_field 的模型应直接校验."""

        class Simple(BaseDataModel):
            x: int

        obj = Simple.from_dict({"x": 42})
        assert isinstance(obj, Simple)
        assert obj.x == 42

    def test_from_type_raw_true(self):
        """from_type(raw=True) 应使用 model_validate."""
        cat = SampleRoot.from_type(
            {"kind": "cat", "name": "Miao", "whiskers": 5}, "cat"
        )
        assert isinstance(cat, SampleCat)
        assert cat.whiskers == 5

    def test_from_type_unknown_raises(self):
        """from_type 未知类型应抛出 ValueError."""
        with pytest.raises(ValueError):
            SampleRoot.from_type({"kind": "fish"}, "fish")

    def test_multiple_discriminator_values(self):
        """一个子类支持多个 discriminator_value."""

        class MultiRoot(BaseDataModel):
            discriminator_field: ClassVar[str] = "type"
            name: str = ""

        class MultiSub(MultiRoot):
            discriminator_value: ClassVar[list[str]] = ["a", "b"]
            extra: int = 0

        a = MultiRoot.from_dict({"type": "a", "name": "A", "extra": 1})
        b = MultiRoot.from_dict({"type": "b", "name": "B", "extra": 2})
        assert isinstance(a, MultiSub)
        assert isinstance(b, MultiSub)
        assert a.extra == 1
        assert b.extra == 2

    def test_indirect_subclass_registers_with_nearest_dispatch_root(self):
        """中间共享基类不应阻断叶子类型向分发根注册."""

        class IndirectRoot(BaseDataModel):
            discriminator_field: ClassVar[str] = "kind"

        class SharedFields(IndirectRoot):
            name: str = ""

        class IndirectLeaf(SharedFields):
            discriminator_value: ClassVar[str] = "leaf"
            value: int

        item = IndirectRoot.from_dict({"kind": "leaf", "name": "shared", "value": 3})
        assert isinstance(item, IndirectLeaf)
        assert item.name == "shared"
        assert item.value == 3

    def test_plain_dto_does_not_pollute_global_registry(self):
        """没有 discriminator_field 的普通 DTO 不应注册到全局基类."""
        marker = "plain-dto-must-not-be-global"

        class PlainDTO(BaseDataModel):
            discriminator_value: ClassVar[str] = marker
            value: int

        assert marker not in BaseDataModel._registry
        assert PlainDTO.model_validate({"value": 1}).value == 1


class TestAutoDispatchList:
    """Test AutoDispatchList automatic dispatch."""

    def test_dispatches_dicts(self):
        """AutoDispatchList 应将 dict 转换为对应的模型实例."""

        class DispatchRoot(BaseDataModel):
            discriminator_field: ClassVar[str] = "type"

        class DispatchA(DispatchRoot):
            discriminator_value: ClassVar[str] = "a"
            val_a: str = ""

        class DispatchB(DispatchRoot):
            discriminator_value: ClassVar[str] = "b"
            val_b: int = 0

        class MyList(AutoDispatchList[DispatchRoot]):
            @classmethod
            def element_type(cls):
                return DispatchRoot

        items = MyList.model_validate(
            [
                {"type": "a", "val_a": "hello"},
                {"type": "b", "val_b": 42},
            ]
        )
        assert len(items.root) == 2
        assert isinstance(items.root[0], DispatchA)
        assert isinstance(items.root[1], DispatchB)
        assert items.root[0].val_a == "hello"
        assert items.root[1].val_b == 42
