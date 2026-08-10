import asyncio
import importlib
import re
import signal
import time
from collections.abc import Coroutine
from enum import StrEnum
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, ParamSpec, Protocol, overload
from uuid import UUID

from butterbot.core.api import BaseApiT
from butterbot.core.context import ApiRegistry, AppContext
from butterbot.core.event import Event, EventBus, SubscriptionHandle
from butterbot.core.exceptions import ConfigError
from butterbot.core.routing import SourceRef
from butterbot.core.source import BaseSource, BaseSourceT
from butterbot.core.types import BaseType
from butterbot.utils.logging_config import LoggingLease, setup_logging

if TYPE_CHECKING:
    from butterbot.core.filter import BaseFilter

from .config import RuntimeConfig
from .health import (
    AppDiagnostics,
    AppHealth,
    AppHealthState,
    EventBusDiagnostic,
    PluginDiagnostic,
    PluginRuntimeDiagnostic,
    SourceDiagnostic,
    TaskDiagnostic,
)
from .shutdown import ShutdownAction, ShutdownRequest
from .source_control import (
    DeclaredSourceDiagnostic,
    DeclaredSourceRef,
    RuntimeSourceController,
)
from .source_factory import SourceFactoryEntry, SourceFactoryRegistry
from .source_manager import SourceManager

_BotSourceP = ParamSpec("_BotSourceP")

_log = getLogger(__name__)


class _OptionalRuntime(Protocol):
    """BotApp 与按配置导入的可选运行时之间的最小边界."""

    @property
    def statuses(self) -> tuple[Any, ...]: ...

    def task_diagnostics(
        self,
    ) -> tuple[tuple[str, int, int, tuple[tuple[str, str], ...]], ...]: ...

    def attach_source(self, source: object) -> None: ...

    def detach_source(self, source_id: object) -> None: ...

    async def register(self) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def fail_start(self, cause: BaseException) -> None: ...

    async def aclose(self) -> None: ...


class _AppState(StrEnum):
    NEW = "new"
    PREPARING = "preparing"
    PREPARED = "prepared"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"
    PREPARE_FAILED = "prepare_failed"


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
        *,
        config_path: str | Path | None = None,
        cli_mode: bool = True,
        logging_mode: Literal["managed", "external"] = "managed",
        close_timeout: float = 5.0,
        max_pending_callbacks: int | None = None,
        ctx: AppContext | None = None,
    ) -> None:
        """初始化 BotApp.

        Args:
            config: 完整运行时配置；与 ``config_path`` 互斥
            config_path: 未注入配置时读取的 YAML 路径
            cli_mode: 是否由独立 CLI 进程托管，决定 ``run()`` 的默认信号策略
            ctx:    可选，注入自定义 AppContext，默认自动创建
            close_timeout: 关闭时等待 in-flight 回调完成的秒数，超时后强制取消
            max_pending_callbacks: 自动创建 EventBus 时可选的回调 task 上限；
                达到上限后 publish 等待容量。注入 ``ctx`` 时该参数必须为 ``None``
            logging_mode: ``managed`` 自动管理进程 root logger;
                ``external`` 保留宿主的日志配置
        Raises:
            FileNotFoundError: 自动加载时 ``config.yaml`` 不存在
            ConfigError: YAML 声明了未知 Source 工厂，或自动实例化失败
        """
        if config is not None and config_path is not None:
            raise ValueError("config 和 config_path 不能同时传入")
        if not isinstance(cli_mode, bool):
            raise TypeError("cli_mode 必须是布尔值")
        self._config = (
            config
            if config is not None
            else RuntimeConfig.from_yaml(config_path or "config.yaml")
        )

        if ctx is not None and max_pending_callbacks is not None:
            raise ValueError("注入 ctx 时不能同时设置 max_pending_callbacks")
        if logging_mode not in ("managed", "external"):
            raise ValueError("logging_mode 必须是 'managed' 或 'external'")

        self._cli_mode = cli_mode
        self._state = _AppState.NEW
        logging_lease = setup_logging() if logging_mode == "managed" else None
        try:
            self._state = _AppState.PREPARING
            # 统一注入对象，传递给各 Source
            self._ctx = ctx or AppContext(
                config=self._config,
                event_bus=EventBus(max_pending_callbacks=max_pending_callbacks),
            )

            # 事件源生命周期管理器
            self._manager = SourceManager(self._ctx)
            self._source_factories = SourceFactoryRegistry.with_defaults()
            self._declared_arguments: dict[
                DeclaredSourceRef, tuple[str, SourceFactoryEntry, dict[str, Any]]
            ] = {}
            self._declared_instances: dict[DeclaredSourceRef, UUID] = {}
            self._declared_last_kind: dict[DeclaredSourceRef, str | None] = {}
            self._source_control = RuntimeSourceController(self)
            self._source_control_lock: asyncio.Lock | None = None
            self._optional_runtime: _OptionalRuntime | None = None
            self._close_timeout = close_timeout
            self._logging_lease: LoggingLease | None = logging_lease
            self._shutdown_event: asyncio.Event | None = None
            self._shutdown_request: ShutdownRequest | None = None
            self._runtime_loop: asyncio.AbstractEventLoop | None = None
            configured_source_ids = self._add_configured_sources()
            try:
                if self._config.plugin_enabled:
                    module = importlib.import_module(
                        "butterbot.plugin.runtime.bootstrap"
                    )
                    factory = getattr(module, "create_optional_runtime")
                    self._optional_runtime = factory(self, self._config)
            except BaseException:
                for source_id in reversed(configured_source_ids):
                    self._manager.discard_unstarted_source(source_id)
                raise
            self._state = _AppState.PREPARED
        except BaseException:
            self._state = _AppState.PREPARE_FAILED
            if logging_lease is not None:
                logging_lease.close()
            raise

    def _add_configured_sources(
        self,
    ) -> list[UUID]:
        """注册 YAML ``kwarg`` 显式声明的 Source 实例."""
        configured: list[
            tuple[DeclaredSourceRef, SourceFactoryEntry, dict[str, Any]]
        ] = []
        definitions = tuple(self._config.source_definitions.values())
        if not any(definition.kwarg for definition in definitions):
            return []

        for definition in definitions:
            for factory_name, arguments in definition.kwarg.items():
                factory_entry = self._source_factories.resolve(
                    definition.source_name,
                    factory_name,
                )
                if factory_entry is None:
                    available = ", ".join(
                        self._source_factories.names(definition.source_name)
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
                reference = DeclaredSourceRef(
                    definition.config_key,
                    factory_entry.factory_id,
                )
                self._declared_arguments[reference] = (
                    definition.source_name,
                    factory_entry,
                    dict(kwargs),
                )
                configured.append(
                    (
                        reference,
                        factory_entry,
                        kwargs,
                    )
                )

        added_source_ids: list[UUID] = []
        for reference, factory_entry, kwargs in configured:
            try:
                source = self._manager.add_source(factory_entry.factory, **kwargs)
                added_source_ids.append(source.uuid)
                self._declared_instances[reference] = source.uuid
                self._declared_last_kind[reference] = source.source_kind
            except BaseException as exc:
                for source_id in reversed(added_source_ids):
                    self._manager.discard_unstarted_source(source_id)
                self._declared_instances.clear()
                if not isinstance(exc, Exception):
                    raise
                if isinstance(exc, ConfigError):
                    raise
                raise ConfigError(
                    "Source 配置 '%s' 自动实例化 '%s' 失败（%s）"
                    % (
                        reference.config_key,
                        factory_entry.factory_id,
                        type(exc).__name__,
                    )
                ) from exc
        return added_source_ids

    # ============ 属性 ============ #

    @property
    def config(self) -> "RuntimeConfig":
        """获取运行时配置（只读）."""
        return self._config

    @property
    def plugin_enabled(self) -> bool:
        """返回最终配置中的插件总开关."""
        return self._config.plugin_enabled

    @property
    def cli_mode(self) -> bool:
        """返回构造期确定的执行宿主模式."""
        return self._cli_mode

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
    def source_control(self) -> RuntimeSourceController:
        """返回只管理 YAML 声明实例的运行期 Source 控制器."""
        return self._source_control

    def _source_control_mutex(self) -> asyncio.Lock:
        lock = self._source_control_lock
        if lock is None:
            lock = asyncio.Lock()
            self._source_control_lock = lock
        return lock

    def _declared_source_diagnostics(
        self,
    ) -> tuple[DeclaredSourceDiagnostic, ...]:
        result: list[DeclaredSourceDiagnostic] = []
        for reference, (source_name, _, _) in self._declared_arguments.items():
            source_id = self._declared_instances.get(reference)
            source = self._manager.get_source(source_id) if source_id else None
            result.append(
                DeclaredSourceDiagnostic(
                    reference=reference,
                    source_name=source_name,
                    source_id=source.uuid if source is not None else None,
                    source_kind=(
                        source.source_kind
                        if source is not None
                        else self._declared_last_kind.get(reference)
                    ),
                    state=(
                        source.health.state.value if source is not None else "absent"
                    ),
                )
            )
        return tuple(result)

    def _require_declared_source(self, reference: DeclaredSourceRef) -> BaseSource:
        if reference not in self._declared_arguments:
            raise ConfigError("事件源声明不存在: %r" % (reference,))
        source_id = self._declared_instances.get(reference)
        source = self._manager.get_source(source_id) if source_id else None
        if source is None:
            raise ConfigError("事件源声明尚未实例化: %r" % (reference,))
        return source

    async def _create_declared_source(
        self,
        reference: DeclaredSourceRef,
        *,
        start: bool,
    ) -> BaseSource:
        if not isinstance(start, bool):
            raise TypeError("start 必须是布尔值")
        async with self._source_control_mutex():
            declaration = self._declared_arguments.get(reference)
            if declaration is None:
                raise ConfigError("事件源声明不存在: %r" % (reference,))
            existing_id = self._declared_instances.get(reference)
            if existing_id is not None and self._manager.get_source(existing_id):
                raise ConfigError("事件源声明已经实例化: %r" % (reference,))
            _, factory_entry, arguments = declaration
            source = self._manager.add_source(
                factory_entry.factory,
                **dict(arguments),
            )
            self._declared_instances[reference] = source.uuid
            self._declared_last_kind[reference] = source.source_kind
            try:
                if self._optional_runtime is not None:
                    self._optional_runtime.attach_source(source)
                if start:
                    await self._manager.start_source(source)
            except BaseException:
                if self._optional_runtime is not None:
                    self._optional_runtime.detach_source(source.uuid)
                try:
                    await self._manager.remove_source(source.uuid)
                finally:
                    self._declared_instances.pop(reference, None)
                raise
            return source

    async def _start_declared_source(self, reference: DeclaredSourceRef) -> BaseSource:
        async with self._source_control_mutex():
            return await self._manager.start_source(
                self._require_declared_source(reference)
            )

    async def _stop_declared_source(self, reference: DeclaredSourceRef) -> BaseSource:
        async with self._source_control_mutex():
            return await self._manager.stop_source(
                self._require_declared_source(reference)
            )

    async def _remove_declared_source(
        self, reference: DeclaredSourceRef
    ) -> BaseSource | None:
        async with self._source_control_mutex():
            if reference not in self._declared_arguments:
                raise ConfigError("事件源声明不存在: %r" % (reference,))
            source_id = self._declared_instances.get(reference)
            if source_id is None:
                return None
            source = self._manager.get_source(source_id)
            if source is None:
                self._declared_instances.pop(reference, None)
                return None
            await self._manager.stop_source(source)
            if self._optional_runtime is not None:
                self._optional_runtime.detach_source(source.uuid)
            removed = await self._manager.remove_source(source.uuid)
            self._declared_instances.pop(reference, None)
            return removed

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
            self._optional_runtime.statuses
            if self._optional_runtime is not None
            else ()
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

    @property
    def diagnostics(self) -> AppDiagnostics:
        """返回应用、Source、插件与框架托管任务的安全快照."""
        plugin_snapshots = (
            self._optional_runtime.task_diagnostics()
            if self._optional_runtime is not None
            else ()
        )
        plugin_runtime = tuple(
            PluginRuntimeDiagnostic(
                plugin_id=plugin_id,
                background_tasks=task_count,
                cleanup_callbacks=cleanup_count,
                pending_callbacks=self.bus.pending_callbacks_for(plugin_id),
            )
            for plugin_id, task_count, cleanup_count, _ in plugin_snapshots
        )
        tasks = [
            TaskDiagnostic(
                owner_type="plugin",
                owner_id=plugin_id,
                task_name=name,
                task_kind="background",
                state=state,
            )
            for plugin_id, _, _, task_snapshots in plugin_snapshots
            for name, state in task_snapshots
        ]
        tasks.extend(
            TaskDiagnostic(
                owner_type=("plugin" if owner != "<application>" else "application"),
                owner_id=owner,
                task_name=name,
                task_kind="event_callback",
                state=state,
            )
            for owner, name, state in self.bus.task_diagnostics()
        )
        return AppDiagnostics(
            health=self.health,
            event_bus=EventBusDiagnostic(
                pending_callbacks=self.bus.pending_callbacks,
                max_pending_callbacks=self.bus.max_pending_callbacks,
            ),
            plugin_runtime=plugin_runtime,
            tasks=tuple(tasks),
        )

    @property
    def shutdown_request(self) -> ShutdownRequest | None:
        """返回已经接受的退出请求；尚未请求时返回 ``None``."""
        return self._shutdown_request

    def request_shutdown(
        self,
        action: ShutdownAction = ShutdownAction.STOP,
        *,
        requested_by: str = "application",
        reason: str | None = None,
    ) -> bool:
        """请求宿主结束运行；首个请求生效并唤醒所有等待者.

        该方法只发出意图，不直接关闭资源，因此可安全地从事件回调中调用。
        ``BotApp.run`` 会在完整关闭后把请求返回给宿主。
        """
        if not isinstance(action, ShutdownAction):
            action = ShutdownAction(action)
        if not requested_by or requested_by != requested_by.strip():
            raise ValueError("requested_by 必须是非空且无首尾空白的字符串")
        if reason is not None:
            if not isinstance(reason, str):
                raise TypeError("reason 必须是字符串或 None")
            reason = reason.strip() or None
        if self._shutdown_request is not None:
            return False
        self._shutdown_request = ShutdownRequest(
            action=action,
            requested_at=time.time(),
            requested_by=requested_by,
            reason=reason,
        )
        event = self._shutdown_event
        loop = self._runtime_loop
        if event is not None and loop is not None:
            loop.call_soon_threadsafe(event.set)
        return True

    async def wait_for_shutdown(self) -> ShutdownRequest:
        """等待并返回首个退出请求，供异步宿主使用."""
        if self._shutdown_request is not None:
            return self._shutdown_request
        if self._shutdown_event is None:
            self._shutdown_event = asyncio.Event()
            self._runtime_loop = asyncio.get_running_loop()
        await self._shutdown_event.wait()
        assert self._shutdown_request is not None
        return self._shutdown_request

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
        self._ensure_prepared()
        if self._optional_runtime is not None:
            await self._optional_runtime.register()
        try:
            await self._manager.start()
        except BaseException as exc:
            if self._optional_runtime is not None:
                await self._optional_runtime.fail_start(exc)
            raise
        if self._optional_runtime is not None:
            try:
                await self._optional_runtime.start()
            except BaseException:
                await self._manager.stop()
                raise
        self._state = _AppState.RUNNING

    async def stop(self) -> None:
        """停止插件生命周期回调和所有事件源."""
        try:
            if self._optional_runtime is not None:
                await self._optional_runtime.stop()
        finally:
            await self._manager.stop()
        if self._state is _AppState.RUNNING:
            self._state = _AppState.PREPARED

    def _ensure_prepared(self) -> None:
        """确保所有启动入口只能使用成功装配的不可变运行时."""
        if self._state is _AppState.PREPARE_FAILED:
            raise RuntimeError("BotApp 准备失败，不能再次启动")
        if self._state in (_AppState.CLOSING, _AppState.CLOSED):
            raise RuntimeError("BotApp 正在关闭或已关闭")

    async def close(self) -> None:
        """关闭应用，释放所有资源.

        关闭顺序是固定的，且不能调换：

        1. 可选插件运行时（若存在）— 逆依赖执行 ``on_stop``，再撤销 Handler、
           close callback 和插件自身资源；
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
        self._state = _AppState.CLOSING
        if self._optional_runtime is not None:
            try:
                await self._optional_runtime.aclose()
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

        bus_closed_cleanly = False
        try:
            await self.bus.close(timeout=self._close_timeout)
        except BaseException as exc:
            if deferred_error is None:
                deferred_error = exc
        else:
            bus_closed_cleanly = True

        apis_closed_cleanly = False
        try:
            await self.api_ctx.aclose_all()
        except BaseException as exc:
            if deferred_error is None:
                deferred_error = exc
        else:
            apis_closed_cleanly = True

        if bus_closed_cleanly and apis_closed_cleanly:
            self._release_logging()
            self._state = _AppState.CLOSED

        if deferred_error is not None:
            raise deferred_error

    def _release_logging(self) -> None:
        """释放由当前应用持有的进程级日志所有权."""
        if self._logging_lease is None:
            return
        self._logging_lease.close()
        self._logging_lease = None

    def __del__(self) -> None:
        try:
            self._release_logging()
        except Exception:
            pass

    # ============ 阻塞式入口 ============ #

    def run(
        self,
        duration: float | None = None,
        *,
        install_signal_handlers: bool | None = None,
        health_reporter: Callable[[AppHealth], None] | None = None,
        health_interval: float = 1.0,
    ) -> ShutdownRequest:
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
            install_signal_handlers: 是否接管 SIGINT/SIGTERM；默认使用 ``cli_mode``
            health_reporter: 可选同步回调，用于 CLI 持久化应用健康快照。
            health_interval: 健康快照报告间隔（秒）。
        """
        if health_reporter is not None and health_interval <= 0:
            raise ValueError("health_interval 必须大于 0")
        if install_signal_handlers is not None and not isinstance(
            install_signal_handlers, bool
        ):
            raise TypeError("install_signal_handlers 必须是布尔值或 None")
        should_install_signals = (
            self._cli_mode
            if install_signal_handlers is None
            else install_signal_handlers
        )

        async def _run() -> ShutdownRequest:
            loop = asyncio.get_running_loop()
            self._runtime_loop = loop
            self._shutdown_event = asyncio.Event()
            if self._shutdown_request is not None:
                self._shutdown_event.set()
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

            if should_install_signals:
                for sig in (signal.SIGINT, signal.SIGTERM):
                    try:
                        loop.add_signal_handler(
                            sig,
                            lambda signal_name=sig.name: self.request_shutdown(
                                ShutdownAction.STOP,
                                requested_by="signal:%s" % signal_name,
                            ),
                        )
                    except (
                        NotImplementedError,
                        RuntimeError,
                        ValueError,
                        AttributeError,
                    ):
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
                            request = await asyncio.wait_for(
                                self.wait_for_shutdown(), timeout=duration
                            )
                        except TimeoutError:
                            _log.info("BotApp 运行 %s 秒，自动停止", duration)
                            self.request_shutdown(
                                ShutdownAction.STOP,
                                requested_by="duration",
                                reason="运行时长已到",
                            )
                            request = await self.wait_for_shutdown()
                        else:
                            _log.info(
                                "BotApp 收到退出请求 %s，正在关闭", request.action
                            )
                    else:
                        request = await self.wait_for_shutdown()
                        _log.info("BotApp 收到退出请求 %s，正在关闭", request.action)
                    return request
            finally:
                if report_task is not None:
                    report_task.cancel()
                    await asyncio.gather(report_task, return_exceptions=True)
                await emit_health()
                for sig in installed:
                    loop.remove_signal_handler(sig)
                self._runtime_loop = None

        try:
            return asyncio.run(_run())
        except KeyboardInterrupt:
            _log.info("BotApp 被用户中断")
            self.request_shutdown(
                ShutdownAction.STOP,
                requested_by="keyboard_interrupt",
            )
            assert self._shutdown_request is not None
            return self._shutdown_request

    # ============ 异步上下文管理器 ============ #

    async def __aenter__(self) -> "BotApp":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
