from uuid import UUID
from typing import Type, Callable, Coroutine, Any, Optional
from logging import getLogger
import asyncio

from .context import RuntimeConfig, APIContext, AppContext
from event import EventBus, Event
from base_cls import BaseSource, BaseSourceT, BaseType, BaseApiT


_log = getLogger(__name__)


class SourceManager:
    """SourceManager 类，负责装配、生命周期和批量管理.

    Attributes:
        config: 运行时配置（只读）
        api_ctx: API 单例容器
        bus: 事件总线
        sources: 事件源集合
    """

    def __init__(self, config: RuntimeConfig):
        """初始化 SourceManager.

        Args:
            config: 运行时配置
        """
        # 核心对象
        self._config = config
        self._api_ctx = APIContext(config)
        self._bus = EventBus()

        # AppContext 统一注入对象
        self._ctx = AppContext(
            config=self._config,
            api_ctx=self._api_ctx,
            bus=self._bus
        )

        # 事件源集合：UUID -> Source
        self._sources: dict[UUID, BaseSource] = {}

        # 生命周期状态
        self._running = False
        self._closed = False

        # 任务管理
        self._tasks: list[asyncio.Task] = []

    # ============ 属性 ============ #

    @property
    def config(self) -> RuntimeConfig:
        """获取运行时配置（只读）."""
        return self._config

    @property
    def ctx(self) -> AppContext:
        """获取应用上下文."""
        return self._ctx

    @property
    def running(self) -> bool:
        """检查是否正在运行."""
        return self._running

    @property
    def closed(self) -> bool:
        """检查是否已关闭."""
        return self._closed

    @property
    def sources(self) -> dict[UUID, BaseSource]:
        """获取所有事件源的副本."""
        return dict(self._sources)

    # ============ Source 管理 ============ #

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

        Raises:
            RuntimeError: 如果 SourceManager 已关闭
        """
        if self._closed:
            raise RuntimeError("SourceManager 已关闭，无法添加事件源")

        source = source_cls(**kwargs)

        self._sources[source.uuid] = source
        _log.info(f"添加事件源: {source.__class__.__name__} (uuid={source.uuid})")
        return source

    def remove_source(self, source_id: UUID) -> Optional[BaseSource]:
        """移除事件源.

        Args:
            source_id: 事件源的 UUID

        Returns:
            被移除的事件源，如果不存在则返回 None
        """
        source = self._sources.pop(source_id, None)
        if source:
            _log.info(f"移除事件源: {source.__class__.__name__} (uuid={source_id})")
        else:
            _log.warning(f"事件源 {source_id} 不存在")
        return source

    def get_source(self, source_id: UUID) -> Optional[BaseSource]:
        """获取事件源.

        Args:
            source_id: 事件源的 UUID

        Returns:
            事件源实例，如果不存在则返回 None
        """
        return self._sources.get(source_id)

    # ============ API 访问 ============ #

    def get_api(self, api_cls: Type[BaseApiT]) -> BaseApiT:
        """获取 API 实例.

        薄封装，内部转发到 api_ctx。

        Args:
            api_cls: API 类类型

        Returns:
            API 单例实例
        """
        return self._api_ctx.get_api(api_cls)

    # ============ 订阅接口（转发 EventBus）============ #

    def subscribe(
        self,
        source_id: UUID,
        status: BaseType
    ) -> Callable:
        """装饰器：订阅事件.

        底层转发到 EventBus，SourceManager 不存 callback 索引表。

        Args:
            source_id: 事件源的 UUID
            status: 状态过滤器

        Returns:
            装饰器函数

        Usage:
            @manager.subscribe(source_id, DynamicType.NEW)
            async def on_new_dynamic(event: Event):
                print(event)
        """
        return self._bus.subscribe(source_id, status)

    def add_subscriber(
        self,
        source_id: UUID,
        callback: Callable[[Event], Coroutine[Any, Any, None]],
        status: BaseType
    ) -> None:
        """添加订阅者.

        底层转发到 EventBus。

        Args:
            source_id: 事件源的 UUID
            callback: 回调函数
            status: 状态过滤器
        """
        self._bus.add_subscriber(source_id, callback, status)

    # ============ 生命周期 ============ #

    async def start(self) -> None:
        """启动 SourceManager.

        生命周期顺序：
        1. 检查状态
        2. 为每个 source 注入上下文 (bind)
        3. 启动每个 source
        """
        if self._closed:
            raise RuntimeError("SourceManager 已关闭，无法启动")

        if self._running:
            _log.warning("SourceManager 已在运行中")
            return

        _log.info("正在启动 SourceManager...")

        # 为每个 source 注入上下文
        for source in self._sources.values():
            source.bind(self._ctx)
            _log.debug(f"绑定上下文到 {source.__class__.__name__}")

        # 启动所有 source
        for source in self._sources.values():
            try:
                await source.start()
                _log.debug(f"启动 {source.__class__.__name__}")
            except Exception as e:
                _log.error(f"启动 {source.__class__.__name__} 失败: {e}")

        self._running = True
        _log.info("SourceManager 已启动")

    async def stop(self) -> None:
        """停止 SourceManager.

        生命周期顺序：
        1. 停止所有 source
        2. 取消所有任务
        """
        if not self._running:
            _log.warning("SourceManager 未在运行")
            return

        _log.info("正在停止 SourceManager...")

        # 停止所有 source
        for source in self._sources.values():
            try:
                await source.stop()
                _log.debug(f"停止 {source.__class__.__name__}")
            except Exception as e:
                _log.error(f"停止 {source.__class__.__name__} 失败: {e}")

        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._tasks.clear()
        self._running = False
        _log.info("SourceManager 已停止")

    async def close(self) -> None:
        """关闭 SourceManager.

        关闭后无法再使用。
        """
        if self._closed:
            return

        # 先停止
        if self._running:
            await self.stop()

        # 清理资源
        self._sources.clear()
        self._closed = True
        _log.info("SourceManager 已关闭")

    # ============ 上下文管理器 ============ #

    async def __aenter__(self) -> "SourceManager":
        """异步上下文管理器入口."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口."""
        await self.close()

    # ============ 便捷方法 ============ #

    def create_task(self, coro: Coroutine) -> asyncio.Task:
        """创建并管理任务.

        SourceManager 统一调度任务，stop 时统一 cancel。

        Args:
            coro: 协程

        Returns:
            创建的任务
        """
        task = asyncio.create_task(coro)
        self._tasks.append(task)

        # 任务完成后自动移除
        def remove_task(t):
            if t in self._tasks:
                self._tasks.remove(t)

        task.add_done_callback(remove_task)
        return task
