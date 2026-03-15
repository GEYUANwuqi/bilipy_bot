# BaseCls模块

此模块提供项目基础的ABC (抽象基类) 和接口定义，供其他模块继承和实现，下面一一介绍各基类的用法

------

## API基类：[BaseApi](base_api.py)

```python
class BaseApi(ABC):

    @abstractmethod
    def __init__(self):
        pass

    @classmethod
    @abstractmethod
    def create(cls, ctx: "APIContext", config_key: str) -> Self:
        """API实例工厂方法"""
        pass

BaseApiT = TypeVar("BaseApiT", bound=BaseApi)
```

此模块仅仅规定一个工厂方法，用于创建api实例本身<br>
`ctx`是**运行时动态创建**的上下文，可以从上下文获取api所需要的config配置，例如cookie等参数<br>
`config_key`是获取配置的配置键，同一配置键对应单个实例<br>
具体实现方法可以参考[napcat_api](../../napcat/api/napcat_api.py)和[bilibili_api](../../bilibili/api/bili_api.py)模块<br>
> 注：通过全局使用一个配置键可以实现全局单例，但是提供了多配置的能力

---------

简单示例：

```python
from base_cls import BaseApi
from typing import Any

class MyApi(BaseApi):

    def __init__(self, cookie: Any):
        self.cookie = cookie

    @classmethod
    def create(cls, ctx: "APIContext", config_key: str) -> "MyApi":
        cookie = ctx.config.get_config(config_key) # 从上下文获取名为{config_key}的配置项
        return cls(cookie)
```

------

## 数据对象混入类：[BaseDataMixin](base_data.py)

```python
class BaseDataMixin:
    """
    框架内约束的数据类混入类, 用于标记框架内数据
    """
    _repr_exclude = {"raw_data"}  # 排除在repr中的属性集合

    def __repr__(self):
        core_properties_str: str = self._get_core_properties_str()
        return f"{self.__class__.__name__}({core_properties_str})"

    def __str__(self):
        return self.__repr__()

    def _get_core_properties_str(self) -> str:
        excludes = set(getattr(self, "_repr_exclude", ()))
        props = {
            k: v
            for k, v in vars(self).items()
            if not k.startswith("_") and k not in excludes
        }
        parts = [f"{k}={repr(v)}" for k, v in props.items()]
        return ", ".join(parts)

BaseDataT = TypeVar("BaseDataT", bound=BaseDataMixin)
```

此混入类**并不强约束**其子类必要有什么属性或方法，主要是提供了一个统一的`__repr__`和`__str__`方法实现，方便子类在调试时输出核心属性信息<br>
子类可以通过定义`_repr_exclude`属性来指定哪些属性**不应该包含在输出**中，默认排除`raw_data`属性<br>
只要这个类混入了`BaseDataMixin`就会被框架认为这是**框架内传输的数据对象**

------

## 基于pydantic的数据对象基类：<br>[BaseDataModel](base_model.py) / [AutoDispatchList](base_model.py)

```python
class BaseDataModel(BaseModel, BaseDataMixin, metaclass=MetaDataModel):
    """
    基于BaseDataMixin实现的领域模型基类
    1. 使用pydantic进行数据校验
    2. 支持单层和多层继承的 discriminator 注册机制
    3. 根类定义 discriminator_field，子类定义 discriminator_value，自动注册到 registry
    """
    model_config = ConfigDict(
        strict = False,  # 强制转换数据
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

BaseDataModelT = TypeVar("BaseDataModelT", bound = BaseDataModel)

class AutoDispatchList(RootModel[list[BaseDataModelT]], Generic[BaseDataModelT]):
    """
    自动对 list 中的 dict 进行 registry 分发
    """

    # root: list[BaseDataModelT]

    # 子类必须指定 element_type
    @classmethod
    def element_type(cls) -> Type[BaseDataModelT]:
        pass

    @model_validator(mode="before")
    @classmethod
    def dispatch_elements(cls, value):
        ...
```

`BaseDataModel`的子类由`MetaDataModel`元类实现自动分发逻辑<br>
`AutoDispatchList`提供了list结构的自动分发<br>
对于此模块的最佳实践，可以参考[napcat事件结构](../napcat/data/__init__.py)和[napcat事件分发逻辑](../napcat/source/napcat_source.py)

------

## 事件源基类：[BaseSource](base_source.py)

```python
class BaseSource(ABC, metaclass=SourceMeta):
    """事件源基类.

    Attributes:
        uuid: 唯一标识符，由 SourceManager 内部管理
        running: 运行状态
    """

    @abstractmethod
    def __init__(self, **kwargs):
        """初始化事件源."""
        self.uuid: UUID = uuid4()
        self.running: bool = False
        self._ctx: "AppContext | None" = None

    @abstractmethod
    async def start(self) -> None:
        """启动事件源.

        子类实现具体的启动逻辑（如开始轮询）。
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止事件源.

        子类实现具体的停止逻辑。
        """
        pass

    def bind(self, ctx: "AppContext") -> None:
        """绑定应用上下文.

        由 SourceManager 在启动时调用，注入依赖。

        Args:
            ctx: 应用上下文
        """
        self._ctx = ctx

    @property
    def ctx(self) -> "AppContext":
        """获取应用上下文."""
        if self._ctx is None:
            raise RuntimeError("Source 尚未绑定上下文，请先调用 bind()")
        return self._ctx

    @property
    def is_running(self) -> bool:
        """检查是否正在运行."""
        return self.running

BaseSourceT = TypeVar("BaseSourceT", bound=BaseSource)
```

`BaseSource`定义了事件源的基本接口，包括启动、停止和绑定上下文的方法<br>
需要注意的是，子类在实现`__init__`时**必须先调用**一次`super().__init__()`来初始化基本属性属性<br>
子类可以在`__init__`时选择传参，**关键字参数**将会在添加到`SourceManager`时传入<br>
> 注：`bind`方法在`SourceManager`启动时调用，当事件源初始化时，它是不持有上下文的

------

## 事件标签基类：[BaseType](base_type.py)

```python
class BaseType(str, Enum):
    """标签枚举基类，提供通用的匹配方法."""

    @property
    def scope(self) -> str:
        """返回标签的作用域."""
        return self.value.split(".", 1)[0]

    @property
    def state(self) -> str:
        """返回标签的状态."""
        return self.value.split(".", 1)[1]

    def matches(self, rule: "BaseType") -> bool:
        """判断状态是否匹配.

        Args:
            rule: 要匹配的标签

        Returns:
            bool: 在作用域相同且具体状态相同或rule为通配符时返回True，否则返回False
        """
        if self.scope == rule.scope:  # 作用域
            if self.state == rule.state:  # 具体状态
                return True
            elif rule.state == "all":  # 通配符
                return True
            else:
                return False
        else:
            return False

BaseTypeT = TypeVar("BaseTypeT", bound=BaseType)
```

提供一个公共的方法`matches()`用于判断两个标签是否匹配<br>
这里的最佳实践可以参考[bilibili事件标签](../bilibili/type/bili_type.py)

------

## 过滤器基类：[BaseFilter](base_filter.py)

--- 待施工 ---
