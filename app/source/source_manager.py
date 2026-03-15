from uuid import UUID
from typing import Type, Any, Optional
from logging import getLogger

from ..context import AppContext
from ..base_cls import BaseSource, BaseSourceT


_log = getLogger(__name__)


class SourceManager:
    """SourceManager 类，专注于事件源的生命周期管理.

    负责添加/移除事件源，并统一管理其启动、停止流程和异步任务。
    高层概念（EventBus、APIContext、AppContext）由 BotApp 持有并通过
    AppContext 注入。

    Attributes:
        sources: 事件源集合（UUID -> Source）
        running: 是否正在运行
        closed: 是否已关闭
    """

    def __init__(self, ctx: AppContext):
        """初始化 SourceManager.

        Args:
            ctx: 由 BotApp 构建并传入的应用上下文
        """
        # 注入应用上下文（只读引用，不持有所有权）
        self._ctx = ctx

        # 事件源集合：UUID -> Source
        self._sources: dict[UUID, BaseSource] = {}

        # 生命周期状态
        self._running = False
        self._closed = False

    # ============ 属性 ============ #

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
