from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, TypeVar
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from bilipy_bot.core.context import AppContext
    from bilipy_bot.core.types import BaseType


class BaseSource(ABC):
    """事件源基类.

    Source 负责：
    - 产生事件数据
    - 通过 EventBus 发布事件
    - 管理自己的生命周期（start/stop）

    Attributes:
        uuid: 唯一标识符，由 SourceManager 内部管理
        running: 运行状态
        config_key: 配置键，子类覆盖此类属性作为默认值
        supported_types: 事件源支持的 ``BaseType`` 枚举类，用于订阅规则编译
    """

    config_key: str = ""

    # 事件源支持的 BaseType 枚举类。子类必须覆盖此属性，
    # 例如 supported_types = DynamicType。
    # 未声明时订阅将抛出 TypeError。
    supported_types: ClassVar[type["BaseType"] | None] = None

    def __init__(self, uuid: UUID | None = None, **kwargs):
        """初始化事件源.

        Args:
            uuid: 可选，指定 UUID，默认自动生成
        """
        self.uuid: UUID = uuid or uuid4()
        self.running: bool = False
        self.config_key: str = kwargs.get("config_key", "")
        self._ctx: AppContext | None = None

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
