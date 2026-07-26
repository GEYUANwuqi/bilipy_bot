import asyncio
from logging import getLogger
from typing import TYPE_CHECKING, Callable, ParamSpec, overload
from uuid import UUID

from butterbot.core.exceptions import LifecycleError, SourceError, SourceStartError
from butterbot.core.source import BaseSource, BaseSourceT

_SourceP = ParamSpec("_SourceP")

if TYPE_CHECKING:
    from butterbot.core.context import AppContext

_log = getLogger(__name__)


class SourceManager:
    """SourceManager 类，专注于事件源的生命周期管理.

    负责添加/移除事件源，并统一管理其启动、停止流程和异步任务。
    高层概念（EventBus、ApiRegistry、AppContext）由 BotApp 持有并通过
    AppContext 注入——因此本类只负责事件源自身及其在 EventBus 上的订阅，
    不负责关闭 EventBus / ApiRegistry（那是 :meth:`BotApp.close` 的职责）。

    Attributes:
        sources: 事件源集合（UUID -> Source）
        running: 是否正在运行
        closed: 是否已关闭
    """

    def __init__(self, ctx: "AppContext"):
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
    def ctx(self) -> "AppContext":
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
        source_cls: Callable[_SourceP, BaseSourceT],
        *args: _SourceP.args,
        **kwargs: _SourceP.kwargs,
    ) -> BaseSourceT:
        """添加事件源.

        本方法只做注册，不启动。应用已在运行时会立即注入上下文，
        以便按"注册 → 订阅 → :meth:`start_source`"的顺序接入新事件源；
        之所以不自动启动，是因为自动启动会让事件在 ``subscribe`` 注册完成前
        就开始产生，从而丢事件。

        Args:
            source_cls: 事件源类
            *args: 事件源初始化位置参数
            **kwargs: 事件源初始化关键字参数

        Returns:
            事件源实例

        Raises:
            LifecycleError: 如果 SourceManager 已关闭
        """
        if self._closed:
            raise LifecycleError("SourceManager 已关闭，无法添加事件源")

        source = source_cls(*args, **kwargs)

        self._sources[source.uuid] = source
        if self._running:
            # 运行中新增：先注入上下文，让用户可以立刻订阅，再显式启动
            source.bind(self._ctx)
            _log.info(
                "运行中添加事件源: %s (uuid=%s)，"
                "请在注册订阅后调用 await start_source(...) 启动",
                source.__class__.__name__,
                source.uuid,
            )
        else:
            _log.info(
                "添加事件源: %s (uuid=%s)", source.__class__.__name__, source.uuid
            )
        return source

    async def remove_source(self, source_id: UUID) -> BaseSource | None:
        """移除事件源.

        完整的移除序列：停止事件源 → 清理它在 EventBus 上的全部订阅 →
        从集合中摘除。只 pop 不做前两步会留下"幽灵源"：
        后台任务仍在跑，且派发表里的回调永久残留。

        Args:
            source_id: 事件源的 UUID

        Returns:
            被移除的事件源，如果不存在则返回 None
        """
        source = self._sources.get(source_id)
        if source is None:
            _log.warning("事件源 %s 不存在", source_id)
            return None

        try:
            await source.stop()
        except Exception:
            _log.exception("移除前停止 %s 失败", source.__class__.__name__)

        removed_callbacks = self._ctx.bus.remove_subscribers(source_id)
        self._sources.pop(source_id, None)
        _log.info(
            "移除事件源: %s (uuid=%s)，同时清理 %s 个订阅回调",
            source.__class__.__name__,
            source_id,
            removed_callbacks,
        )
        return source

    @overload
    def get_source(self, source: UUID) -> BaseSource | None: ...

    @overload
    def get_source(
        self, source: type[BaseSourceT], config_key: str | None = None
    ) -> BaseSourceT | None: ...

    def get_source(
        self,
        source: type[BaseSource] | UUID,
        config_key: str | None = None,
    ) -> BaseSource | None:
        """获取事件源.

        支持三种查找方式：

        - ``get_source(source_id)`` — 按 UUID 查找
        - ``get_source(source_cls)`` — 按类型查找（单一实例时最常用）
        - ``get_source(source_cls, config_key)`` — 按类型 + 配置键查找（同源多实例时区分）

        Args:
            source: 事件源类或 UUID
            config_key: 配置键，可选。传入时做精确匹配，否则返回该类型的第一个实例

        Returns:
            事件源实例，如果不存在则返回 None
        """
        # 按 UUID 查找
        if isinstance(source, UUID):
            return self._sources.get(source)

        # 此时 source 一定是 type[BaseSource]
        source_cls: type[BaseSource] = source

        # 按类型查找（可选精确匹配 config_key）
        for inst in self._sources.values():
            if isinstance(inst, source_cls):
                if config_key is None or inst.config_key == config_key:
                    return inst
        return None

    def _require_source(self, source: BaseSource | UUID) -> BaseSource:
        """解析并校验事件源必须已注册.

        Args:
            source: 事件源实例或其 UUID

        Returns:
            已注册的事件源实例

        Raises:
            SourceError: 事件源未注册
        """
        source_id = source if isinstance(source, UUID) else source.uuid
        found = self._sources.get(source_id)
        if found is None:
            raise SourceError("事件源 %s 不存在，请先通过 add_source 添加" % source_id)
        return found

    # ============ 单个 Source 的运行时启停 ============ #

    async def start_source(self, source: BaseSource | UUID) -> BaseSource:
        """启动单个事件源（可在应用运行中调用）.

        用于运行期动态接入新事件源：``add_source`` → ``subscribe`` →
        ``await start_source(...)``。重复调用是安全的
        （:meth:`BaseSource.start` 对已运行的源直接返回）。

        Args:
            source: 事件源实例或其 UUID

        Returns:
            被启动的事件源

        Raises:
            LifecycleError: SourceManager 已关闭
            SourceError: 事件源未注册
        """
        if self._closed:
            raise LifecycleError("SourceManager 已关闭，无法启动事件源")

        resolved = self._require_source(source)
        resolved.bind(self._ctx)
        await resolved.start()
        _log.info("启动事件源: %s (uuid=%s)", type(resolved).__name__, resolved.uuid)
        return resolved

    async def stop_source(self, source: BaseSource | UUID) -> BaseSource:
        """停止单个事件源，但保留注册与订阅（可再次 :meth:`start_source`）.

        Args:
            source: 事件源实例或其 UUID

        Returns:
            被停止的事件源

        Raises:
            SourceError: 事件源未注册
        """
        resolved = self._require_source(source)
        await resolved.stop()
        _log.info("停止事件源: %s (uuid=%s)", type(resolved).__name__, resolved.uuid)
        return resolved

    # ============ 生命周期 ============ #

    async def start(self) -> None:
        """启动 SourceManager.

        生命周期顺序：

        1. 检查状态
        2. 为每个 source 注入上下文 (bind)
        3. 启动每个 source

        任一事件源启动失败时不留半启动状态：已成功启动的会被回滚（stop），
        然后把全部失败聚合成 :class:`SourceStartError` 上抛，``running`` 保持 ``False``。

        Raises:
            LifecycleError: SourceManager 已关闭
            SourceStartError: 一个或多个事件源启动失败
        """
        if self._closed:
            raise LifecycleError("SourceManager 已关闭，无法启动")

        if self._running:
            _log.warning("SourceManager 已在运行中")
            return

        _log.info("正在启动 SourceManager...")

        # 为每个 source 注入上下文
        for source in self._sources.values():
            source.bind(self._ctx)
            _log.debug("绑定上下文到 %s", source.__class__.__name__)

        # 启动所有 source
        started: list[BaseSource] = []
        failures: dict[str, BaseException] = {}
        for source in self._sources.values():
            try:
                await source.start()
            except Exception as e:
                _log.exception("启动 %s 失败", source.__class__.__name__)
                failures["%s(uuid=%s)" % (source.__class__.__name__, source.uuid)] = e
            else:
                started.append(source)
                _log.debug("启动 %s", source.__class__.__name__)

        if failures:
            for source in started:
                try:
                    await source.stop()
                except Exception:
                    _log.exception("回滚 %s 时出错", source.__class__.__name__)
            raise SourceStartError(failures)

        self._running = True
        _log.info("SourceManager 已启动")

    async def stop(self) -> None:
        """停止 SourceManager.

        依次停止所有事件源；单个事件源停止失败只记录日志，不影响其余事件源。

        ``CancelledError`` 被单独接住：Ctrl+C 路径下 ``await source.stop()``
        会在取消态抛出它，而它不是 ``Exception`` 的子类——不单独处理就会
        中断后续事件源的清理。这里先清完所有事件源，最后再把取消向上重抛。

        Raises:
            asyncio.CancelledError: 停止过程中被取消（在清理完成后重抛）
        """
        if not self._running:
            _log.warning("SourceManager 未在运行")
            return

        _log.info("正在停止 SourceManager...")

        cancelled: asyncio.CancelledError | None = None

        # 停止所有 source
        for source in self._sources.values():
            try:
                await source.stop()
                _log.debug("停止 %s", source.__class__.__name__)
            except asyncio.CancelledError as e:
                cancelled = e
                _log.warning(
                    "停止 %s 时被取消，继续清理其余事件源",
                    source.__class__.__name__,
                )
            except Exception:
                _log.exception("停止 %s 失败", source.__class__.__name__)

        self._running = False
        _log.info("SourceManager 已停止")

        if cancelled is not None:
            raise cancelled

    async def close(self) -> None:
        """关闭 SourceManager.

        关闭后无法再使用。即使 :meth:`stop` 因取消而抛出，
        集合清理与状态置位仍会完成（在 ``finally`` 中）。
        """
        if self._closed:
            return

        try:
            # 先停止
            if self._running:
                await self.stop()
        finally:
            # 清理资源
            self._sources.clear()
            self._closed = True
            _log.info("SourceManager 已关闭")
