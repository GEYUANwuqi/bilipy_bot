from __future__ import annotations

from typing import TYPE_CHECKING

from bilipy_bot.core.event import EventBus

from .api_registry import ApiRegistry

if TYPE_CHECKING:
    from bilipy_bot.app.config import RuntimeConfig


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
        config: "RuntimeConfig",
        event_bus: EventBus | None = None,
        api_ctx: ApiRegistry | None = None,
    ):
        """初始化 AppContext.

        Args:
            config: 运行时配置
            event_bus: 可选，注入自定义 EventBus，默认自动创建
            api_ctx: 可选，注入自定义 ApiRegistry，默认自动创建
        """
        self._config = config
        self._api_ctx = api_ctx or ApiRegistry(config)
        self._bus = event_bus or EventBus()

    @property
    def config(self) -> "RuntimeConfig":
        """获取运行时配置（只读）."""
        return self._config

    @property
    def api_ctx(self) -> ApiRegistry:
        """获取 API 上下文."""
        return self._api_ctx

    @property
    def bus(self) -> EventBus:
        """获取事件总线."""
        return self._bus
