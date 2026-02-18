from typing import ClassVar, Self
from pydantic import BaseModel, ConfigDict
from pydantic._internal._model_construction import ModelMetaclass
from .base_data import BaseDataMixin


class MetaDataModel(ModelMetaclass):
    """pydantic数据模型元类，支持单层和多层继承的 discriminator 注册机制.
    1. 根类定义 discriminator_field，子类定义 discriminator_value，自动注册到 registry
    2. 支持属性嵌套
    3. 完全自动注册和分发
    """
    def __new__(mcls, name, bases, namespace, **kwargs):
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)

        # 找到最近的带 registry 的父类
        base_with_registry = None
        for base in bases:
            if hasattr(base, "_registry"):
                base_with_registry = base
                break

        discriminator_value = namespace.get("discriminator_value")
        discriminator_field = namespace.get("discriminator_field")

        # 如果子类有 discriminator_value，注册到父类的 registry
        if base_with_registry and discriminator_value is not None:
            if isinstance(discriminator_value, (list, tuple, set)):
                for value in discriminator_value:
                    base_with_registry._registry[value] = cls
            else:
                base_with_registry._registry[discriminator_value] = cls

        # 如果当前类定义了 discriminator_field，初始化自己的 registry（用于二级分发）
        if discriminator_field is not None:
            cls._registry = {}

        return cls


class BaseDataModel(BaseModel, BaseDataMixin, metaclass=MetaDataModel):
    """
    基于BaseDataMixin实现的领域模型基类
    1. 使用pydantic进行数据校验
    2. 支持单层和多层继承的 discriminator 注册机制
    3. 根类定义 discriminator_field，子类定义 discriminator_value，自动注册到 registry
    """
    model_config = ConfigDict(
        strict = True,  # 严格模式，强制转换数据
        frozen = True,  # 实例不可变，自动生成 __hash__
        extra = 'ignore',  # 额外字段将被忽略
    )

    # discriminator_field: ClassVar[str] = "data_type"
    # 作为分发依据的"键"，必须在根/基类定义
    # discriminator_value: ClassVar[str] = "group"
    # 作为分发依据的"值"，子类可选定义，若定义则认为是可直接构造模型，否则则认为是属性嵌套的分发模型

    _registry: ClassVar[dict] = {}

    @classmethod
    def from_raw(cls, raw: dict) -> Self:
        """从原始数据构造实例，可实现复杂构造逻辑

        Args:
            raw: 原始数据字典

        Returns:
            对应子类的实例
        """
        pass

    @classmethod
    def from_dict(cls, raw: dict) -> Self:
        """从dict自动构造实例，支持多层分发

        Args:
            raw: 原始数据字典

        Returns:
            对应子类的实例
        """
        field = getattr(cls, 'discriminator_field', None)
        if field is None:
            # 没有 discriminator_field，直接构造
            return cls.model_validate(raw)

        value = raw.get(field)
        if value is None:
            raise ValueError(f"Missing discriminator field: {field}")

        subclass = cls._registry.get(value)
        if subclass is None:
            raise ValueError(f"Unknown type value: {value}")

        # 递归检查子类是否还有自己的 discriminator_field（多层分发）
        sub_field = getattr(subclass, 'discriminator_field', None)
        if sub_field is not None and sub_field != field and hasattr(subclass, '_registry') and subclass._registry:
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
            raise ValueError(f"Unknown type value: {type_value}")
        if raw:
            return subclass.model_validate(data)
        else:
            return subclass.from_raw(data)

    def __repr__(self):
        # 覆盖BaseModel的__repr__，使用BaseDataMixin的实现
        return super().__repr__()

    def __str__(self):
        return self.__repr__()
