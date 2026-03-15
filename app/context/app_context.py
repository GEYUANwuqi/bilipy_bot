from .api_context import APIContext
from .config import RuntimeConfig
from ..event import EventBus


class AppContext:
    """应用上下文，统一注入对象.

    用于将分散的依赖注入整合为一个对象，
    供 Source 和其他组件使用。

    Attributes:
        config: 运行时配置（只读）
        api_ctx: API 单例容器
        bus: 事件总线
    """

    def __init__(
        self,
        config: RuntimeConfig,
        api_ctx: APIContext,
        bus: EventBus
    ):
        """初始化 AppContext.

        Args:
            config: 运行时配置
            api_ctx: API 上下文
            bus: 事件总线
        """
        self._config = config
        self._api_ctx = api_ctx
        self._bus = bus

    @property
    def config(self) -> RuntimeConfig:
        """获取运行时配置（只读）."""
        return self._config

    @property
    def api_ctx(self) -> APIContext:
        """获取 API 上下文."""
        return self._api_ctx

    @property
    def bus(self) -> EventBus:
        """获取事件总线."""
        return self._bus
