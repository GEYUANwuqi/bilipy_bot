from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, TypeVar
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from butter_bot.core.context import AppContext
    from butter_bot.core.types import BaseType


class BaseSource(ABC):
    """事件源基类.

    Source 负责：
    - 产生事件数据
    - 通过 EventBus 发布事件
    - 管理自己的生命周期（start/stop）

    子类只需实现 :meth:`on_start` 和 :meth:`on_stop`，
    无需手动管理 ``self.running`` 状态——
    :meth:`start` 和 :meth:`stop` 已自动处理。

    Attributes:
        uuid: 唯一标识符，由 SourceManager 内部管理
        running: 运行状态（由 start/stop 自动管理，子类不应直接修改）
        config_key: 配置键，子类可覆盖此类属性作为默认值
        supported_types: 事件源支持的 ``BaseType`` 枚举类，用于订阅规则编译
    """

    config_key: str = ""

    # 事件源支持的 BaseType 枚举类。子类必须覆盖此属性，
    # 例如 supported_types = DynamicType。
    # 未声明时订阅将抛出 TypeError。
    supported_types: ClassVar[type["BaseType"] | None] = None

    def __init_subclass__(cls) -> None:
        """子类初始化检查."""
        super().__init_subclass__()

        if cls.__name__ == "BaseSource":
            return

        if not hasattr(cls, "supported_types"):
            raise TypeError(f"{cls.__name__} must define supported_types")

    def __init__(
        self,
        uuid: UUID | None = None,
        *,
        config_key: str | None = None,
    ) -> None:
        """初始化事件源.

        Args:
            uuid: 可选，指定 UUID，默认自动生成
            config_key: 可选，覆盖类级默认配置键
        """
        self.uuid: UUID = uuid or uuid4()
        self.running: bool = False
        self._ctx: "AppContext | None" = None
        if config_key is not None:
            self.config_key = config_key

    async def start(self) -> None:
        """启动事件源（模板方法）.

        自动管理 ``running`` 状态，然后委托给 :meth:`on_start`。
        子类不应重写此方法，应实现 :meth:`on_start`。

        :meth:`on_start` 抛出异常（含 ``CancelledError``）时，
        ``running`` 会回滚为 ``False`` 后再向上传播——否则启动失败的事件源
        会以"运行中"的假象留在应用里，而它的资源其实从未建立起来。

        Raises:
            Exception: :meth:`on_start` 抛出的任何异常，原样向上传播
        """
        if self.running:
            return
        self.running = True
        try:
            await self.on_start()
        except BaseException:
            self.running = False
            raise

    async def stop(self) -> None:
        """停止事件源（模板方法）.

        自动管理 ``running`` 状态，然后委托给 :meth:`on_stop`。
        子类不应重写此方法，应实现 :meth:`on_stop`。
        """
        if not self.running:
            return
        self.running = False
        await self.on_stop()

    @abstractmethod
    async def on_start(self) -> None:
        """子类实现：事件源启动逻辑.

        在 :meth:`start` 中被调用，此时 ``self.running`` 已为 ``True``。
        """

    @abstractmethod
    async def on_stop(self) -> None:
        """子类实现：事件源停止逻辑.

        在 :meth:`stop` 中被调用，此时 ``self.running`` 已为 ``False``。
        """

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
