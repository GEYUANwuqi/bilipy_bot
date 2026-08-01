import asyncio
import re
import signal
import time
from collections.abc import Coroutine
from logging import getLogger
from typing import TYPE_CHECKING, Any, Callable, ParamSpec, overload
from uuid import UUID

from butterbot.core.api import BaseApiT
from butterbot.core.context import ApiRegistry, AppContext
from butterbot.core.event import Event, EventBus, SubscriptionHandle
from butterbot.core.exceptions import ConfigError
from butterbot.core.source import BaseSource, BaseSourceT
from butterbot.core.types import BaseType
from butterbot.plugin.contracts.routing import SourceRef

if TYPE_CHECKING:
    from butterbot.core.filter import BaseFilter
    from butterbot.plugin.runtime.manager import PluginManager

from .config import RuntimeConfig
from .health import (
    AppHealth,
    AppHealthState,
    PluginDiagnostic,
    SourceDiagnostic,
)
from .source_factory import SourceFactoryEntry, SourceFactoryRegistry
from .source_manager import SourceManager

_BotSourceP = ParamSpec("_BotSourceP")

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

    def __init__(
        self,
        config: RuntimeConfig | None = None,
        ctx: AppContext | None = None,
        *,
        close_timeout: float = 5.0,
        max_pending_callbacks: int | None = None,
        source_factory_registry: SourceFactoryRegistry | None = None,
    ) -> None:
        """初始化 BotApp.

        Args:
            config: 运行时配置，可选，默认从 ``config.yaml`` 自动加载
            ctx:    可选，注入自定义 AppContext，默认自动创建
            close_timeout: 关闭时等待 in-flight 回调完成的秒数，超时后强制取消
            max_pending_callbacks: 自动创建 EventBus 时可选的回调 task 上限；
                达到上限后 publish 等待容量。注入 ``ctx`` 时该参数必须为 ``None``
            source_factory_registry: 可选的 YAML Source 工厂注册表。默认使用内置
                Bilibili 和 NapCat Source；只在配置包含 ``kwarg`` 时使用

        Raises:
            FileNotFoundError: 自动加载时 ``config.yaml`` 不存在
            ConfigError: YAML 声明了未知 Source 工厂，或自动实例化失败
        """
        self._config = config or RuntimeConfig.from_yaml()

        if ctx is not None and max_pending_callbacks is not None:
            raise ValueError("注入 ctx 时不能同时设置 max_pending_callbacks")

        # 统一注入对象，传递给各 Source
        self._ctx = ctx or AppContext(
            config=self._config,
            event_bus=EventBus(max_pending_callbacks=max_pending_callbacks),
        )

        # 事件源生命周期管理器
        self._manager = SourceManager(self._ctx)
        self._plugin_manager: PluginManager | None = None
        self._add_configured_sources(source_factory_registry)

        self._close_timeout = close_timeout

    def _add_configured_sources(
        self,
        registry: SourceFactoryRegistry | None,
    ) -> None:
        """注册 YAML ``kwarg`` 显式声明的 Source 实例."""
        configured: list[tuple[str, SourceFactoryEntry, dict[str, Any]]] = []
        definitions = tuple(self._config.source_definitions.values())
        if not any(definition.kwarg for definition in definitions):
            return

        resolved_registry = registry or SourceFactoryRegistry.with_defaults()
        for definition in definitions:
            for factory_name, arguments in definition.kwarg.items():
                factory_entry = resolved_registry.resolve(
                    definition.source_name,
                    factory_name,
                )
                if factory_entry is None:
                    available = ", ".join(
                        resolved_registry.names(definition.source_name)
                    )
                    raise ConfigError(
                        "Source 配置 '%s' 的自动实例 '%s' 未注册；"
                        "source_name='%s' 可用工厂: %s"
                        % (
                            definition.config_key,
                            factory_name,
                            definition.source_name,
                            available or "无",
                        )
                    )
                kwargs = dict(arguments)
                kwargs["config_key"] = definition.config_key
                configured.append(
                    (
                        definition.config_key,
                        factory_entry,
                        kwargs,
                    )
                )

        added_source_ids: list[UUID] = []
        for config_key, factory_entry, kwargs in configured:
            try:
                if factory_entry.owner_id is None:
                    source = self._manager.add_source(factory_entry.factory, **kwargs)
                else:
                    source = self._manager.add_owned_source(
                        factory_entry.owner_id,
                        factory_entry.factory,
                        **kwargs,
                    )
                added_source_ids.append(source.uuid)
            except BaseException as exc:
                for source_id in reversed(added_source_ids):
                    self._manager.discard_unstarted_source(source_id)
                if not isinstance(exc, Exception):
                    raise
                raise ConfigError(
                    "Source 配置 '%s' 自动实例化 '%s' 失败（%s）"
                    % (config_key, factory_entry.factory_id, type(exc).__name__)
                ) from exc

    # ============ 属性 ============ #

    @property
    def config(self) -> "RuntimeConfig":
        """获取运行时配置（只读）."""
        return self._config

    @property
    def bus(self) -> EventBus:
        """获取事件总线."""
        return self._ctx.bus

    @property
    def api_ctx(self) -> ApiRegistry:
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

    @property
    def health(self) -> AppHealth:
        """聚合应用、Source 和插件的非敏感诊断快照."""
        sources = tuple(
            SourceDiagnostic(
                source_id=str(source.uuid),
                source_type=type(source).__name__,
                source_kind=source.source_kind,
                config_key=source.config_key,
                state=source.health.state.value,
                last_success_at=source.health.last_success_at,
                last_error_at=source.health.last_error_at,
                last_error_type=source.health.last_error_type,
            )
            for source in self._manager.sources.values()
        )
        plugin_statuses = (
            self._plugin_manager.statuses if self._plugin_manager is not None else ()
        )
        plugins = tuple(
            PluginDiagnostic(
                plugin_id=status.plugin_id,
                state=status.state.value,
                failure_types=tuple(failure.error_type for failure in status.failures),
            )
            for status in plugin_statuses
        )

        if self._manager.closed:
            state = AppHealthState.STOPPED
        elif self._manager.stop_failed:
            state = AppHealthState.DEGRADED
        elif self._manager.closing:
            state = AppHealthState.STOPPING
        elif self._manager.running:
            state = (
                AppHealthState.READY
                if all(source.healthy for source in sources)
                and all(plugin.healthy for plugin in plugins)
                else AppHealthState.DEGRADED
            )
        else:
            state = AppHealthState.STOPPED

        return AppHealth(
            state=state,
            observed_at=time.time(),
            sources=sources,
            plugins=plugins,
        )

    def _attach_plugin_manager(self, manager: "PluginManager") -> None:
        """由插件 bootstrap 绑定唯一插件控制面."""
        if self._plugin_manager is not None:
            raise RuntimeError("BotApp 已绑定 PluginManager")
        self._plugin_manager = manager

    async def _prepare_plugins(self) -> None:
        """执行插件运行阶段注册，不启动 Source."""
        if self._plugin_manager is not None:
            await self._plugin_manager.register()

    # ============ Source 管理（委托 SourceManager）============ #

    def add_source(
        self,
        source_cls: Callable[_BotSourceP, BaseSourceT],
        *args: _BotSourceP.args,
        **kwargs: _BotSourceP.kwargs,
    ) -> BaseSourceT:
        """添加事件源.

        Args:
            source_cls: 事件源类
            *args: 事件源初始化位置参数
            **kwargs: 事件源初始化关键字参数

        Returns:
            事件源实例

        Note:
            只做注册，不启动。应用已在运行中时，接入顺序为
            ``add_source`` → ``subscribe`` → ``await start_source(...)``。
        """
        return self._manager.add_source(source_cls, *args, **kwargs)

    def _add_owned_source(
        self,
        owner_id: str,
        source_cls: Callable[_BotSourceP, BaseSourceT],
        *args: _BotSourceP.args,
        **kwargs: _BotSourceP.kwargs,
    ) -> BaseSourceT:
        """由插件 registrar 为已校验 owner 注册 Source."""
        return self._manager.add_owned_source(
            owner_id,
            source_cls,
            *args,
            **kwargs,
        )

    async def remove_source(self, source_id: UUID) -> BaseSource | None:
        """移除事件源.

        会先停止该事件源，再清理它在 EventBus 上的全部订阅，最后摘除。

        Args:
            source_id: 事件源的 UUID

        Returns:
            被移除的事件源，不存在时返回 ``None``
        """
        return await self._manager.remove_source(source_id)

    async def start_source(self, source: BaseSource | UUID) -> BaseSource:
        """启动单个事件源（用于运行期动态接入）.

        Args:
            source: 事件源实例或其 UUID

        Returns:
            被启动的事件源
        """
        return await self._manager.start_source(source)

    async def stop_source(self, source: BaseSource | UUID) -> BaseSource:
        """停止单个事件源，保留注册与订阅（可再次 :meth:`start_source`）.

        Args:
            source: 事件源实例或其 UUID

        Returns:
            被停止的事件源
        """
        return await self._manager.stop_source(source)

    @overload
    def get_source(self, source: UUID) -> BaseSource | None: ...

    @overload
    def get_source(self, source: SourceRef) -> BaseSource | None: ...

    @overload
    def get_source(
        self, source: type[BaseSourceT], config_key: str | None = None
    ) -> BaseSourceT | None: ...

    def get_source(
        self,
        source: type[BaseSource] | SourceRef | UUID,
        config_key: str | None = None,
    ) -> BaseSource | None:
        """获取事件源.

        支持三种查找方式：

        - ``app.get_source(source_id)`` — 按 UUID 查找
        - ``app.get_source(source_cls)`` — 按类型查找（单一实例时最常用）
        - ``app.get_source(source_cls, config_key)`` — 按类型 + 配置键查找（同源多实例时区分）
        """
        if isinstance(source, (UUID, SourceRef)):
            return self._manager.get_source(source)
        return self._manager.get_source(source, config_key)

    def get_sources(self, source_ref: SourceRef) -> tuple[BaseSource, ...]:
        """返回逻辑 SourceRef 匹配的全部事件源."""
        return self._manager.get_sources(source_ref)

    # ============ API 访问（委托 ApiRegistry）============ #

    def get_api(self, api_cls: type[BaseApiT], config_key: str) -> BaseApiT:
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
        status: str | re.Pattern[str] | BaseType,
        *,
        event_filter: "BaseFilter | None" = None,
        owner_id: str | None = None,
    ) -> Callable:
        """装饰器：订阅事件.

        Args:
            source_id: 事件源的 UUID
            status: 状态过滤器（``BaseType`` 枚举、``str`` 或 ``re.Pattern`` 正则）
            event_filter: 可选的事件内容过滤器，只有通过过滤器的事件才触发回调
            owner_id: 可选的注册所有者标识

        Returns:
            装饰器函数

        Usage:
            @app.subscribe(source.uuid, LiveType.OPEN)
            async def on_open(event: Event):
                ...

            @app.subscribe(source.uuid, r".*\\.message")
            async def on_message(event: Event):
                ...

            pattern = re.compile(r"danmaku\\.(msg|gift)")
            @app.subscribe(source.uuid, pattern)
            async def on_danmaku(event: Event):
                ...
        """
        source = self._manager.get_source(source_id)
        if source is None:
            raise ValueError("事件源 %s 不存在，请先通过 add_source 添加" % source_id)
        return self.bus.subscribe(
            source_id,
            status,
            source.supported_types,
            event_filter=event_filter,
            owner_id=owner_id,
        )

    def add_subscriber(
        self,
        source_id: UUID,
        callback: Callable[[Event], Coroutine[Any, Any, None]],
        status: str | re.Pattern[str] | BaseType,
        *,
        event_filter: "BaseFilter | None" = None,
        owner_id: str | None = None,
    ) -> SubscriptionHandle:
        """手动注册订阅者.

        Args:
            source_id: 事件源的 UUID
            callback: 异步回调函数
            status: 状态过滤器（``BaseType`` 枚举、``str`` 或 ``re.Pattern`` 正则）
            event_filter: 可选的事件内容过滤器，只有通过过滤器的事件才触发回调
            owner_id: 可选的注册所有者标识

        Returns:
            可用于精确退订的不透明句柄
        """
        source = self._manager.get_source(source_id)
        if source is None:
            raise ValueError("事件源 %s 不存在，请先通过 add_source 添加" % source_id)
        return self.bus.add_subscriber(
            source_id,
            callback,
            status,
            source.supported_types,
            event_filter=event_filter,
            owner_id=owner_id,
        )

    def unsubscribe(self, source_id: UUID) -> int:
        """取消某个事件源的全部订阅.

        Args:
            source_id: 事件源的 UUID

        Returns:
            被移除的回调数量
        """
        return self.bus.remove_subscribers(source_id)

    # ============ 生命周期 ============ #

    async def start(self) -> None:
        """启动应用、所有事件源和插件生命周期回调.

        Raises:
            SourceStartError: 一个或多个事件源启动失败
                （抛出前已回滚成功启动的事件源）
            PluginRegistrationError: 插件配置、Handler 注册或启动回调失败
        """
        if self._plugin_manager is not None:
            await self._plugin_manager.register()
        try:
            await self._manager.start()
        except BaseException as exc:
            if self._plugin_manager is not None:
                await self._plugin_manager.fail_start(exc)
            raise
        if self._plugin_manager is not None:
            try:
                await self._plugin_manager.start()
            except BaseException:
                await self._manager.stop()
                raise

    async def stop(self) -> None:
        """停止插件生命周期回调和所有事件源."""
        try:
            if self._plugin_manager is not None:
                await self._plugin_manager.stop()
        finally:
            await self._manager.stop()

    async def close(self) -> None:
        """关闭应用，释放所有资源.

        关闭顺序是固定的，且不能调换：

        1. experimental ``PluginManager.aclose()``（若存在）— 逆依赖执行
           ``on_stop``，再撤销 Handler、close callback、插件 Source 和配置
           registry；
        2. ``SourceManager.close()`` — 停止全部事件源并清空注册；
           先停源，总线才不会在排空期间又收到新事件。
        3. ``EventBus.close()`` — 排空正在执行的订阅回调（``close_timeout`` 超时后取消）；
           先排空回调，回调里才不会用到下一步已经关掉的 API。
        4. ``ApiRegistry.aclose_all()`` — 释放各 API 持有的连接与后台任务。

        插件关闭失败会被延迟到 Source、EventBus 与 API 完成清理后传播。
        Source 关闭失败时不会继续关闭 EventBus 与 API，因为失败 Source 仍由
        manager 持有并可能依赖这些对象完成下一次清理；调用方修正瞬时故障后可
        再次调用 ``close()``。Source 全部停止后，EventBus 即使关闭失败也仍会
        尝试释放 API。
        """
        deferred_error: BaseException | None = None
        if self._plugin_manager is not None:
            try:
                await self._plugin_manager.aclose()
            except BaseException as exc:
                deferred_error = exc

        try:
            await self._manager.close()
        except BaseException as manager_error:
            if isinstance(deferred_error, asyncio.CancelledError):
                deferred_error.add_note(
                    "SourceManager 关闭同时失败: %s: %s"
                    % (type(manager_error).__name__, manager_error)
                )
                raise deferred_error
            raise

        try:
            await self.bus.close(timeout=self._close_timeout)
        except BaseException as exc:
            if deferred_error is None:
                deferred_error = exc

        try:
            await self.api_ctx.aclose_all()
        except BaseException as exc:
            if deferred_error is None:
                deferred_error = exc

        if deferred_error is not None:
            raise deferred_error

    # ============ 阻塞式入口 ============ #

    def run(
        self,
        duration: float | None = None,
        *,
        health_reporter: Callable[[AppHealth], None] | None = None,
        health_interval: float = 1.0,
    ) -> None:
        """阻塞运行 BotApp，直到被中断或达到指定时长.

        这是最简使用方式，适合大多数场景。
        高级用户仍可使用 ``async with`` 或 ``await start/stop`` 进行精细控制。

        ``SIGINT``（Ctrl+C）与 ``SIGTERM``（容器 ``docker stop`` / k8s 缩容）
        都会触发**正常退出路径**：先跳出等待，再走完整的 :meth:`close`。
        只依赖 ``KeyboardInterrupt`` 的话，容器里收到 SIGTERM 会直接被杀，
        清理代码根本不会执行。不支持 ``add_signal_handler`` 的平台
        （如 Windows 的 ProactorEventLoop）自动回退到 ``KeyboardInterrupt``。

        Args:
            duration: 可选，运行时长（秒）。为 ``None`` 则持续运行直到收到信号。
            health_reporter: 可选同步回调，用于 CLI 持久化应用健康快照。
            health_interval: 健康快照报告间隔（秒）。
        """
        if health_reporter is not None and health_interval <= 0:
            raise ValueError("health_interval 必须大于 0")

        async def _run() -> None:
            loop = asyncio.get_running_loop()
            stop_event = asyncio.Event()
            installed: list[signal.Signals] = []
            report_task: asyncio.Task[None] | None = None

            async def emit_health() -> None:
                if health_reporter is None:
                    return
                try:
                    await asyncio.to_thread(health_reporter, self.health)
                except Exception:
                    _log.exception("健康快照回调执行失败")

            async def report_health() -> None:
                while True:
                    await asyncio.sleep(health_interval)
                    await emit_health()

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, stop_event.set)
                except (NotImplementedError, RuntimeError, ValueError, AttributeError):
                    _log.debug("当前平台不支持处理信号 %s，回退到默认行为", sig)
                else:
                    installed.append(sig)

            try:
                async with self:
                    if health_reporter is not None:
                        await emit_health()
                        report_task = asyncio.create_task(report_health())
                    if duration is not None:
                        try:
                            await asyncio.wait_for(stop_event.wait(), timeout=duration)
                        except TimeoutError:
                            _log.info("BotApp 运行 %s 秒，自动停止", duration)
                        else:
                            _log.info("BotApp 收到停止信号，正在关闭")
                    else:
                        await stop_event.wait()
                        _log.info("BotApp 收到停止信号，正在关闭")
            finally:
                if report_task is not None:
                    report_task.cancel()
                    await asyncio.gather(report_task, return_exceptions=True)
                await emit_health()
                for sig in installed:
                    loop.remove_signal_handler(sig)

        try:
            asyncio.run(_run())
        except KeyboardInterrupt:
            _log.info("BotApp 被用户中断")

    # ============ 异步上下文管理器 ============ #

    async def __aenter__(self) -> "BotApp":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
