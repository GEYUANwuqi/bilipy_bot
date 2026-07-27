from typing import ClassVar, Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, RootModel, model_validator

from .base_data import BaseDataMixin


class BaseDataModel(BaseModel, BaseDataMixin):
    """
    基于BaseDataMixin实现的领域模型基类
    1. 使用pydantic进行数据校验
    2. 支持单层和多层继承的 discriminator 注册机制
    3. 根类定义 discriminator_field，子类定义 discriminator_value，自动注册到 registry
    """

    model_config = ConfigDict(
        strict=False,  # 强制转换数据
        frozen=True,  # 实例不可变，自动生成 __hash__
        extra="ignore",  # 额外字段将被忽略
    )

    # discriminator_field: ClassVar[str] = "data_type"
    # 作为分发依据的"键"，必须在根/基类定义
    # discriminator_value: ClassVar[str] = "group"
    # 作为分发依据的"值"，子类可选定义，若定义则认为是可直接构造模型，否则则认为是属性嵌套的分发模型

    _registry: ClassVar[dict] = {}

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs) -> None:
        """在 Pydantic 完成基础模型初始化后注册 discriminator."""
        super().__pydantic_init_subclass__(**kwargs)

        # 沿直接父类的 MRO 查找最近的分发根，支持共享字段中间类，
        # 同时避免普通 DTO 注册到 BaseDataModel 的全局 registry。
        base_with_registry = None
        for base in cls.__bases__:
            for ancestor in base.__mro__:
                if (
                    "discriminator_field" in ancestor.__dict__
                    and "_registry" in ancestor.__dict__
                ):
                    base_with_registry = ancestor
                    break
            if base_with_registry is not None:
                break

        discriminator_value = cls.__dict__.get("discriminator_value")
        discriminator_field = cls.__dict__.get("discriminator_field")

        if base_with_registry is not None and discriminator_value is not None:
            if isinstance(discriminator_value, (list, tuple, set)):
                for value in discriminator_value:
                    base_with_registry._registry[value] = cls
            else:
                base_with_registry._registry[discriminator_value] = cls

        if discriminator_field is not None:
            cls._registry = {}

    @classmethod
    def from_raw(cls, raw: dict) -> Self:
        """从原始数据构造实例，可实现复杂构造逻辑

        Args:
            raw: 原始数据字典

        Returns:
            对应子类的实例
        """
        ...

    @classmethod
    def from_dict(cls, raw: dict) -> Self:
        """从dict自动构造实例，支持多层分发

        Args:
            raw: 原始数据字典

        Returns:
            对应子类的实例
        """
        field = getattr(cls, "discriminator_field", None)
        if field is None:
            # 没有 discriminator_field，直接构造
            return cls.model_validate(raw)

        value = raw.get(field)
        if value is None:
            raise ValueError("Missing discriminator field: %s" % field)

        subclass = cls._registry.get(value)
        if subclass is None:
            raise ValueError("Unknown type value: %s" % value)

        # 递归检查子类是否还有自己的 discriminator_field（多层分发）
        sub_field = getattr(subclass, "discriminator_field", None)
        if (
            sub_field is not None
            and sub_field != field
            and hasattr(subclass, "_registry")
            and subclass._registry
        ):
            # 子类有自己的 discriminator_field，继续递归分发
            return subclass.from_dict(raw)
        else:
            # 子类没有 discriminator_field，直接构造
            return subclass.model_validate(raw)

    @classmethod
    def from_type(cls, data: dict, type_value: str, raw: bool = True) -> Self:
        """根据指定的type_value从dict构造实例

        Args:
            data: 原始数据字典
            type_value: discriminator_value的值，用于匹配具体子类
            raw: 是否从model_validate方法构造实例，
                 否则调用子类的from_raw方法.

        Returns:
            对应子类的实例
        """
        subclass = cls._registry.get(type_value)
        if subclass is None:
            raise ValueError("Unknown type value: %s" % type_value)
        if raw:
            return subclass.model_validate(data)
        else:
            return subclass.from_raw(data)

    def __repr__(self):
        # 覆盖BaseModel的__repr__，使用BaseDataMixin的实现
        return BaseDataMixin.__repr__(self)

    def __str__(self):
        return self.__repr__()


BaseDataModelT = TypeVar("BaseDataModelT", bound=BaseDataModel)


class AutoDispatchList(RootModel[list[BaseDataModelT]], Generic[BaseDataModelT]):
    """
    自动对 list 中的 dict 进行 registry 分发
    """

    # root: list[BaseDataModelT]

    # 子类必须指定 element_type
    @classmethod
    def element_type(cls) -> type[BaseDataModelT]: ...

    @model_validator(mode="before")
    @classmethod
    def dispatch_elements(cls, value):
        if not isinstance(value, list):
            return value

        result = []
        for item in value:
            if isinstance(item, dict):
                result.append(cls.element_type().from_dict(item))
            else:
                result.append(item)

        return result

    # 辅助方法，方便调试和展示

    def __repr__(self):
        core_properties_str: str = self._get_core_properties_str()
        return "%s(%s)" % (self.__class__.__name__, core_properties_str)

    def __str__(self):
        return self.__repr__()

    def _get_core_properties_str(self) -> str:
        excludes = {"raw_data"}
        props = {
            k: v
            for k, v in vars(self).items()
            if not k.startswith("_") and k not in excludes
        }
        parts = ["%s=%r" % (k, v) for k, v in props.items()]
        return ", ".join(parts)
