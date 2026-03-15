from uuid import UUID
from typing import Type, Callable, Coroutine, Any
from logging import getLogger

from .event import EventBus, Event
from .source import SourceManager
from .context import AppContext, RuntimeConfig
from .base_cls import BaseSourceT, BaseType, BaseApiT


_log = getLogger(__name__)


class BotApp:
    """Bot 应用主入口，持有所有高层基础设施.

    BotApp 负责：
    - 持有并构建 RuntimeConfig、EventBus、AppContext
    - 创建并持有 SourceManager（专注于事件源生命周期）
    - 对外暴露订阅、事件源管理、API 访问和生命周期接口

    Attributes:
        config:  运行时配置（只读）
        ctx:     应用上下文（注入给各 Source）
        manager: 事件源生命周期管理器
    """

    def __init__(self, config: RuntimeConfig) -> None:
        """初始化 BotApp.

        Args:
            config: 运行时配置
        """
        self._config = config

        # 统一注入对象，传递给各 Source
        self._ctx = AppContext(
            config=self._config,
        )

        # 事件源生命周期管理器
        self._manager = SourceManager(self._ctx)

    # ============ 属性 ============ #

    @property
    def config(self) -> RuntimeConfig:
        """获取运行时配置（只读）."""
        return self._config

    @property
    def bus(self) -> EventBus:
        """获取事件总线."""
        return self._ctx.bus

    @property
    def api_ctx(self):
        return self._ctx.api_ctx

    @property
    def ctx(self) -> AppContext:
        """获取应用上下文."""
        return self._ctx

    @property
    def manager(self) -> SourceManager:
        """获取事件源管理器."""
        return self._manager

    @property
    def running(self) -> bool:
        """检查是否正在运行."""
        return self._manager.running

    @property
    def closed(self) -> bool:
        """检查是否已关闭."""
        return self._manager.closed

    # ============ Source 管理（委托 SourceManager）============ #

    def add_source(
        self,
        source_cls: Type[BaseSourceT],
        **kwargs: Any
    ) -> BaseSourceT:
        """添加事件源.

        Args:
            source_cls: 事件源类
            **kwargs: 事件源初始化关键字参数

        Returns:
            事件源实例
        """
        return self._manager.add_source(source_cls, **kwargs)

    def remove_source(self, source_id: UUID):
        """移除事件源."""
        return self._manager.remove_source(source_id)

    def get_source(self, source_id: UUID):
        """获取事件源."""
        return self._manager.get_source(source_id)

    # ============ API 访问（委托 APIContext）============ #

    def get_api(self, api_cls: Type[BaseApiT], config_key: str) -> BaseApiT:
        """获取 API 单例实例.

        Args:
            api_cls: API 类类型
            config_key: 配置键

        Returns:
            API 单例实例
        """
        return self.api_ctx.get_api(api_cls, config_key)

    # ============ 订阅接口（委托 EventBus）============ #

    def subscribe(
        self,
        source_id: UUID,
        status: BaseType,
    ) -> Callable:
        """装饰器：订阅事件.

        Args:
            source_id: 事件源的 UUID
            status: 状态过滤器

        Returns:
            装饰器函数

        Usage:
            @app.subscribe(source.uuid, LiveType.OPEN)
            async def on_open(event: Event):
                ...
        """
        return self.bus.subscribe(source_id, status)

    def add_subscriber(
        self,
        source_id: UUID,
        callback: Callable[[Event], Coroutine[Any, Any, None]],
        status: BaseType,
    ) -> None:
        """手动注册订阅者.

        Args:
            source_id: 事件源的 UUID
            callback: 异步回调函数
            status: 状态过滤器
        """
        self.bus.add_subscriber(source_id, callback, status)

    # ============ 生命周期（委托 SourceManager）============ #

    async def start(self) -> None:
        """启动应用（启动所有事件源）."""
        await self._manager.start()

    async def stop(self) -> None:
        """停止应用（停止所有事件源）."""
        await self._manager.stop()

    async def close(self) -> None:
        """关闭应用，释放所有资源."""
        await self._manager.close()

    # ============ 异步上下文管理器 ============ #

    async def __aenter__(self) -> "BotApp":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
