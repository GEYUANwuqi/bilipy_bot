from abc import ABC, abstractmethod
from uuid import uuid4, UUID
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.context import AppContext


class BaseSource(ABC):
    """事件源基类.

    Source 负责：
    - 产生事件数据
    - 通过 EventBus 发布事件
    - 管理自己的生命周期（start/stop）

    Attributes:
        uuid: 唯一标识符，由 BiliBiliManager 内部管理
        running: 运行状态
    """

    def __init__(self):
        """初始化事件源."""
        self.uuid: UUID = uuid4()
        self.running: bool = False
        self._ctx: "AppContext | None" = None

    def bind(self, ctx: "AppContext") -> None:
        """绑定应用上下文.

        由 BiliBiliManager 在启动时调用，注入依赖。

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

    @abstractmethod
    def add_members(self, keys: list) -> None:
        """添加监控成员.

        Args:
            keys: 监控成员标识列表
        """
        pass

    @abstractmethod
    def remove_members(self, keys: list) -> None:
        """移除监控成员.

        Args:
            keys: 监控成员标识列表
        """
        pass

    @property
    def is_running(self) -> bool:
        """检查是否正在运行."""
        return self.running
