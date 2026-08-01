import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, TypeVar
from uuid import UUID, uuid4

from butterbot.core.exceptions import LifecycleError

if TYPE_CHECKING:
    from butterbot.core.context import AppContext
    from butterbot.core.types import BaseType


class SourceState(str, Enum):
    """Source 生命周期状态."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOP_FAILED = "stop_failed"


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
        source_kind: 可选的逻辑事件源类型，用于注册期 SourceRef 解析
        config_key: 配置键，子类可覆盖此类属性作为默认值
        supported_types: 事件源支持的 ``BaseType`` 枚举类，用于订阅规则编译
    """

    source_kind: ClassVar[str | None] = None
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
        self._state = SourceState.STOPPED
        self._cleanup_required = False
        self._lifecycle_lock = asyncio.Lock()
        self._ctx: "AppContext | None" = None
        if config_key is not None:
            self.config_key = config_key

    async def start(self) -> None:
        """启动事件源（模板方法）.

        自动管理 ``running`` 状态，然后委托给 :meth:`on_start`。
        子类不应重写此方法，应实现 :meth:`on_start`。

        :meth:`on_start` 抛出异常（含 ``CancelledError``）时，
        ``running`` 会回滚为 ``False``，并调用 :meth:`on_stop` 清理部分初始化，
        然后传播原始异常。回滚清理也失败时保留 ``cleanup_required``，后续
        :meth:`stop` 可以重试。

        Raises:
            Exception: :meth:`on_start` 抛出的任何异常，原样向上传播
        """
        async with self._lifecycle_lock:
            if self._state is SourceState.RUNNING:
                return
            if self._cleanup_required:
                raise LifecycleError(
                    "%s 上一次停止尚未清理完成，请先重试 stop()" % type(self).__name__
                )

            self._state = SourceState.STARTING
            self.running = True
            # on_start 可能先创建部分资源再失败，因此进入回调前就取得清理责任。
            self._cleanup_required = True
            try:
                await self.on_start()
            except BaseException as start_error:
                self.running = False
                self._state = SourceState.STOPPING
                try:
                    await self.on_stop()
                except BaseException as cleanup_error:
                    self._state = SourceState.STOP_FAILED
                    if cleanup_error is not start_error:
                        start_error.add_note(
                            "%s 启动回滚失败: %s: %s"
                            % (
                                type(self).__name__,
                                type(cleanup_error).__name__,
                                cleanup_error,
                            )
                        )
                else:
                    self._cleanup_required = False
                    self._state = SourceState.STOPPED
                raise
            else:
                self._state = SourceState.RUNNING

    async def stop(self) -> None:
        """停止事件源（模板方法）.

        自动管理 ``running`` 状态，然后委托给 :meth:`on_stop`。
        子类不应重写此方法，应实现 :meth:`on_stop`。回调失败或被取消时保留
        清理责任，下一次调用会再次执行 :meth:`on_stop`。
        """
        async with self._lifecycle_lock:
            if not self._cleanup_required:
                return

            # 先清除 running，让依赖该标志退出的循环停止产生新工作；
            # cleanup_required 独立保留，失败后下一次 stop() 仍会重试。
            self.running = False
            self._state = SourceState.STOPPING
            try:
                await self.on_stop()
            except BaseException:
                self._state = SourceState.STOP_FAILED
                raise
            else:
                self._cleanup_required = False
                self._state = SourceState.STOPPED

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

    @property
    def state(self) -> SourceState:
        """返回当前生命周期状态."""
        return self._state

    @property
    def cleanup_required(self) -> bool:
        """是否仍持有必须由 :meth:`stop` 释放的资源责任."""
        return self._cleanup_required


BaseSourceT = TypeVar("BaseSourceT", bound=BaseSource)
