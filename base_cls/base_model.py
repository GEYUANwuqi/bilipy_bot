from pydantic import BaseModel, ConfigDict
from pydantic._internal._model_construction import ModelMetaclass
from .base_data import BaseDataMixin


class DataModelMeta(ModelMetaclass):
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

        # 如果当前类定义了 discriminator_field，说明它是根类
        if "discriminator_field" in namespace:
            cls._registry = {}

        # 如果是子类，且有 discriminator_value，则注册
        elif base_with_registry and discriminator_value is not None:
            if isinstance(discriminator_value, (list, tuple, set)):
                for value in discriminator_value:
                    base_with_registry._registry[value] = cls
            else:
                base_with_registry._registry[discriminator_value] = cls

        return cls


class BaseDataModel(BaseModel, BaseDataMixin, metaclass=DataModelMeta):
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
    discriminator_field = "base_type"
    _registry = {}

    @classmethod
    def from_dict(cls, raw: dict):
        """从dict自动构造实例"""
        field = cls.discriminator_field
        value = raw.get(field)

        if value is None:
            raise ValueError(f"Missing discriminator field: {field}")

        subclass = cls._registry.get(value)  # 运行时动态添加属性
        if subclass is None:
            raise ValueError(f"Unknown {field}: {value}")

        return subclass.model_validate(raw)
