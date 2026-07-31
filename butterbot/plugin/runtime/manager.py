from __future__ import annotations

import asyncio
import inspect
from collections.abc import Coroutine, Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import StrEnum
from logging import getLogger
from typing import TYPE_CHECKING, Any

from butterbot.core.exceptions import LifecycleError
from butterbot.plugin.contracts.context import PluginScope
from butterbot.plugin.contracts.hooks import iter_configure_hooks
from butterbot.plugin.discovery.catalog import LoadedPlugin, PluginCatalog
from butterbot.plugin.discovery.settings import PluginLifecyclePolicy
from butterbot.plugin.errors import PluginRegistrationError

from .registrar import (
    ConfigRegistrar,
    PluginRegistrar,
    RegistrationReceipt,
    make_receipt,
)

if TYPE_CHECKING:
    from butterbot.app.bot_app import BotApp
    from butterbot.app.config import ConfigBuilderRegistry
    from butterbot.app.source_factory import SourceFactoryRegistry

_log = getLogger(__name__)


class PluginState(StrEnum):
    """插件从发现到关闭的控制面状态."""

    VALIDATED = "validated"
    CONFIGURING = "configuring"
    CONFIGURED = "configured"
    REGISTERING = "registering"
    REGISTERED = "registered"
    STARTED = "started"
    FAILED = "failed"
    BLOCKED = "blocked"
    CLOSED = "closed"


class PluginFailurePhase(StrEnum):
    """可持久诊断且不包含异常消息的插件失败阶段."""

    CONFIGURING = "configuring"
    REGISTERING = "registering"
    STARTING = "starting"
    STOPPING = "stopping"
    CLEANING = "cleaning"
    BACKGROUND = "background"
    SOURCE_START = "source_start"


@dataclass(frozen=True, slots=True)
class PluginFailure:
    """不泄露配置和异常消息的插件失败记录."""

    plugin_id: str
    phase: PluginFailurePhase
    error_type: str
    timed_out: bool = False
    cancelled: bool = False


@dataclass(frozen=True, slots=True)
class PluginStatus:
    """不包含配置值和 secret 的插件诊断快照."""

    plugin_id: str
    plugin_name: str
    version: str
    state: PluginState
    origin_kind: str
    origin: str
    fingerprint: str | None
    error: str | None = None
    failures: tuple[PluginFailure, ...] = ()

    @property
    def healthy(self) -> bool:
        """当前是否没有记录到生命周期或后台资源失败."""
        return not self.failures


@dataclass(slots=True)
class _PluginRecord:
    loaded: LoadedPlugin
    state: PluginState = PluginState.VALIDATED
    error: str | None = None
    failures: list[PluginFailure] = dataclass_field(default_factory=list)

    @property
    def plugin_id(self) -> str:
        return self.loaded.descriptor.plugin_id


class PluginManager:
    """编排可信启动期插件的配置、注册、生命周期回调和逆序清理."""

    def __init__(
        self,
        catalog: PluginCatalog,
        builder_registry: "ConfigBuilderRegistry",
        factory_registry: "SourceFactoryRegistry",
        *,
        plugin_settings: Mapping[str, Mapping[str, object]] | None = None,
        lifecycle: PluginLifecyclePolicy | None = None,
    ) -> None:
        self._catalog = catalog
        self._builder_registry = builder_registry
        self._factory_registry = factory_registry
        self._plugin_settings = plugin_settings or {}
        self._lifecycle = lifecycle or PluginLifecyclePolicy()
        self._records = {
            item.descriptor.plugin_id: _PluginRecord(item) for item in catalog.plugins
        }
        self._config_registrars: dict[str, ConfigRegistrar] = {}
        self._runtime_registrars: dict[str, PluginRegistrar] = {}
        self._app: BotApp | None = None
        self._configured = False
        self._registered = False
        self._closed = False

    @property
    def plugin_ids(self) -> tuple[str, ...]:
        return self._catalog.plugin_ids

    @property
    def statuses(self) -> tuple[PluginStatus, ...]:
        return tuple(
            PluginStatus(
                plugin_id=record.plugin_id,
                plugin_name=record.loaded.plugin_name,
                version=record.loaded.descriptor.version,
                state=record.state,
                origin_kind=record.loaded.origin.kind,
                origin=record.loaded.origin.location,
                fingerprint=record.loaded.origin.fingerprint,
                error=record.error,
                failures=tuple(record.failures),
            )
            for record in self._ordered_records()
        )

    @property
    def failures(self) -> tuple[PluginFailure, ...]:
        """返回按插件拓扑和发生顺序排列的失败记录."""
        return tuple(
            failure for record in self._ordered_records() for failure in record.failures
        )

    @property
    def receipts(self) -> tuple[RegistrationReceipt, ...]:
        receipts: list[RegistrationReceipt] = []
        for plugin_id in self.plugin_ids:
            if self._records[plugin_id].state not in (
                PluginState.FAILED,
                PluginState.REGISTERED,
                PluginState.STARTED,
            ):
                continue
            config = self._config_registrars.get(plugin_id)
            runtime = self._runtime_registrars.get(plugin_id)
            if (
                config is not None
                and runtime is not None
                and not config.closed
                and not runtime.closed
            ):
                receipts.append(make_receipt(config, runtime))
        return tuple(receipts)

    def configure(self) -> None:
        """按依赖顺序执行无运行时副作用的 ``@configure`` 方法."""
        if self._closed:
            raise LifecycleError("PluginManager 已关闭")
        if self._configured:
            return

        for record in self._ordered_records():
            plugin_id = record.plugin_id
            registrar = ConfigRegistrar(
                plugin_id,
                self._builder_registry,
                self._factory_registry,
                settings=self._plugin_settings.get(plugin_id),
                resource_root=record.loaded.origin.resource_root,
            )
            self._config_registrars[plugin_id] = registrar
            record.state = PluginState.CONFIGURING
            try:
                record.loaded.instance._bind_context(
                    plugin_id,
                    self._plugin_settings.get(plugin_id),
                    record.loaded.origin.resource_root,
                    lambda phase, cause, owner=plugin_id: self._record_failure(
                        owner,
                        PluginFailurePhase(phase),
                        cause,
                    ),
                    plugin_name=record.loaded.plugin_name,
                )
                for hook in iter_configure_hooks(record.loaded.instance):
                    result = hook(registrar)
                    if inspect.isawaitable(result):
                        if inspect.iscoroutine(result):
                            result.close()
                        raise TypeError("@configure 方法必须是同步函数")
                registrar.commit()
            except BaseException as exc:
                registrar.rollback()
                self._mark_failure(
                    plugin_id,
                    PluginFailurePhase.CONFIGURING,
                    exc,
                )
                self._rollback_config()
                self._mark_rolled_back()
                self._closed = True
                if not isinstance(exc, Exception):
                    raise
                raise PluginRegistrationError(
                    plugin_id,
                    "configuring",
                    exc,
                ) from exc
            record.state = PluginState.CONFIGURED
        self._configured = True

    def bind(self, app: "BotApp") -> None:
        """绑定已构建应用，并接管配置 factory 创建的插件 Source."""
        if self._closed:
            raise LifecycleError("PluginManager 已关闭")
        if not self._configured:
            raise LifecycleError("PluginManager 尚未完成配置阶段")
        if self._app is not None:
            raise LifecycleError("PluginManager 已绑定应用")

        self._app = app
        try:
            for plugin_id in self.plugin_ids:
                registrar = PluginRegistrar(
                    app,
                    plugin_id,
                    drain_timeout=self._lifecycle.drain_timeout,
                    report_failure=lambda phase, cause, owner=plugin_id: (
                        self._record_failure(
                            owner,
                            PluginFailurePhase(phase),
                            cause,
                        )
                    ),
                )
                self._runtime_registrars[plugin_id] = registrar
                record = self._records[plugin_id]
                record.loaded.instance._bind_runtime_context(
                    get_source=app.get_source,
                    get_sources=app.get_sources,
                    get_api=app.get_api,
                )
                for entry in app.manager.source_catalog.by_owner(plugin_id):
                    registrar.adopt_source(entry.source_id)
        except BaseException:
            for registrar in self._runtime_registrars.values():
                for source_id in registrar.source_ids:
                    app.manager.discard_unstarted_source(source_id)
            self._rollback_config()
            self._mark_rolled_back()
            self._runtime_registrars.clear()
            self._app = None
            self._closed = True
            raise

    def abort_before_bind(self) -> None:
        """应用构造失败时同步撤销配置阶段注册."""
        if self._app is not None:
            raise LifecycleError("已绑定应用的 PluginManager 必须异步关闭")
        self._rollback_config()
        self._mark_rolled_back()
        self._closed = True

    async def register(self) -> None:
        """按依赖顺序登记 ``@register`` Handler，失败时回滚全部注册."""
        if self._closed:
            raise LifecycleError("PluginManager 已关闭")
        failed_ids = tuple(
            record.plugin_id
            for record in self._ordered_records()
            if record.state in (PluginState.FAILED, PluginState.BLOCKED)
        )
        if failed_ids:
            raise LifecycleError(
                "插件停止或清理失败，不能重新启动: %s" % ", ".join(failed_ids)
            )
        if self._registered:
            return
        if self._app is None:
            raise LifecycleError("PluginManager 尚未绑定应用")

        for record in self._ordered_records():
            plugin_id = record.plugin_id
            registrar = self._runtime_registrars[plugin_id]
            record.state = PluginState.REGISTERING
            try:
                for spec in record.loaded.instance._subscription_specs():
                    registrar.add_subscription(spec)
                registrar.commit()
            except BaseException as exc:
                self._mark_failure(
                    plugin_id,
                    PluginFailurePhase.REGISTERING,
                    exc,
                )
                cleanup_cancelled = await self._rollback_all()
                if not isinstance(exc, Exception):
                    raise
                if cleanup_cancelled is not None:
                    raise cleanup_cancelled
                raise PluginRegistrationError(
                    plugin_id,
                    "registering",
                    exc,
                ) from exc
            record.state = PluginState.REGISTERED
        self._registered = True

    async def start(self) -> None:
        """Source 全部启动成功后按依赖顺序执行 ``on_start``."""
        if self._closed:
            raise LifecycleError("PluginManager 已关闭")
        if not self._registered:
            raise LifecycleError("PluginManager 尚未完成注册阶段")
        if all(
            record.state == PluginState.STARTED for record in self._ordered_records()
        ):
            return

        started_ids: list[str] = []
        for record in self._ordered_records():
            if record.state != PluginState.REGISTERED:
                continue
            plugin_id = record.plugin_id
            try:
                record.loaded.instance.context.scope._start()
                await self._run_callback(
                    record.loaded.instance.on_start,
                    name="on_start",
                    timeout=self._lifecycle.start_timeout,
                    scope=record.loaded.instance.context.scope,
                )
            except BaseException as exc:
                stop_cancelled = await self._run_stop_callbacks(
                    tuple(reversed((*started_ids, plugin_id)))
                )
                self._mark_failure(
                    plugin_id,
                    PluginFailurePhase.STARTING,
                    exc,
                )
                cleanup_cancelled = await self._rollback_all()
                if not isinstance(exc, Exception):
                    raise
                if stop_cancelled is not None:
                    raise stop_cancelled
                if cleanup_cancelled is not None:
                    raise cleanup_cancelled
                raise PluginRegistrationError(
                    plugin_id,
                    "starting",
                    exc,
                ) from exc
            record.state = PluginState.STARTED
            started_ids.append(plugin_id)

    async def stop(self) -> None:
        """在 Source 停止前按依赖逆序执行 ``on_stop``."""
        if self._closed:
            return
        plugin_ids = tuple(
            record.plugin_id
            for record in reversed(self._ordered_records())
            if record.state == PluginState.STARTED
        )
        cancelled = await self._run_stop_callbacks(plugin_ids)
        if cancelled is not None:
            raise cancelled

    async def fail_start(self, cause: BaseException) -> None:
        """Source 启动失败时撤销所有插件注册."""
        for record in self._ordered_records():
            if record.state in (PluginState.REGISTERED, PluginState.STARTED):
                record.state = PluginState.FAILED
                self._record_failure(
                    record.plugin_id,
                    PluginFailurePhase.SOURCE_START,
                    cause,
                )
        cleanup_cancelled = await self._rollback_all()
        if cleanup_cancelled is not None:
            raise cleanup_cancelled

    async def aclose(self) -> None:
        """按依赖逆序关闭插件，并撤销配置 registry."""
        if self._closed:
            return
        plugin_ids = tuple(
            record.plugin_id
            for record in reversed(self._ordered_records())
            if record.state == PluginState.STARTED
        )
        callback_cancelled = await self._run_stop_callbacks(plugin_ids)
        runtime_cancelled = await self._close_runtime()
        self._rollback_config()
        self._closed = True
        for record in self._ordered_records():
            if record.state not in (PluginState.FAILED, PluginState.BLOCKED):
                record.state = (
                    PluginState.FAILED
                    if self._has_cleanup_failure(record)
                    else PluginState.CLOSED
                )
        if callback_cancelled is not None:
            raise callback_cancelled
        if runtime_cancelled is not None:
            raise runtime_cancelled

    async def _run_stop_callbacks(
        self,
        plugin_ids: tuple[str, ...],
    ) -> asyncio.CancelledError | None:
        cancelled: asyncio.CancelledError | None = None
        for plugin_id in plugin_ids:
            record = self._records[plugin_id]
            failure_count = len(record.failures)
            try:
                await self._run_callback(
                    record.loaded.instance.on_stop,
                    name="on_stop",
                    timeout=self._lifecycle.stop_timeout,
                    scope=record.loaded.instance.context.scope,
                )
            except asyncio.CancelledError as exc:
                self._record_failure(
                    plugin_id,
                    PluginFailurePhase.STOPPING,
                    exc,
                )
                cancelled = cancelled or exc
            except Exception as exc:
                self._record_failure(
                    plugin_id,
                    PluginFailurePhase.STOPPING,
                    exc,
                )
                _log.exception("插件 '%s' 的 on_stop 回调失败", plugin_id)
            try:
                await record.loaded.instance.context.scope._close(
                    self._lifecycle.cleanup_timeout
                )
            except asyncio.CancelledError as exc:
                self._record_failure(
                    plugin_id,
                    PluginFailurePhase.CLEANING,
                    exc,
                )
                cancelled = cancelled or exc
            except Exception as exc:
                self._record_failure(
                    plugin_id,
                    PluginFailurePhase.CLEANING,
                    exc,
                )
                _log.exception("插件 '%s' 的资源作用域清理失败", plugin_id)
            if record.state == PluginState.STARTED:
                record.state = (
                    PluginState.FAILED
                    if any(
                        failure.phase
                        in (
                            PluginFailurePhase.CLEANING,
                            PluginFailurePhase.STOPPING,
                        )
                        for failure in record.failures[failure_count:]
                    )
                    else PluginState.REGISTERED
                )
        return cancelled

    async def _rollback_all(self) -> asyncio.CancelledError | None:
        cancelled = await self._close_runtime()
        self._rollback_config()
        self._registered = False
        self._closed = True
        self._mark_rolled_back()
        return cancelled

    async def _close_runtime(self) -> asyncio.CancelledError | None:
        cancelled: asyncio.CancelledError | None = None
        for plugin_id in reversed(self.plugin_ids):
            scope = self._records[plugin_id].loaded.instance.context.scope
            if scope.task_count or scope.cleanup_count:
                try:
                    await scope._close(self._lifecycle.cleanup_timeout)
                except asyncio.CancelledError as exc:
                    self._record_failure(
                        plugin_id,
                        PluginFailurePhase.CLEANING,
                        exc,
                    )
                    cancelled = cancelled or exc
                except Exception as exc:
                    self._record_failure(
                        plugin_id,
                        PluginFailurePhase.CLEANING,
                        exc,
                    )
                    _log.exception("插件 '%s' 的剩余资源清理失败", plugin_id)
            registrar = self._runtime_registrars.get(plugin_id)
            if registrar is None:
                continue
            try:
                await _run_bounded(
                    registrar.aclose(),
                    timeout=self._lifecycle.cleanup_timeout,
                    name="butterbot.plugin.cleanup",
                )
            except asyncio.CancelledError as exc:
                self._record_failure(
                    plugin_id,
                    PluginFailurePhase.CLEANING,
                    exc,
                )
                cancelled = cancelled or exc
            except Exception as exc:
                self._record_failure(
                    plugin_id,
                    PluginFailurePhase.CLEANING,
                    exc,
                )
                _log.exception("插件 '%s' 的运行时注册清理失败", plugin_id)
        return cancelled

    def _rollback_config(self) -> None:
        for plugin_id in reversed(self.plugin_ids):
            registrar = self._config_registrars.get(plugin_id)
            if registrar is not None:
                registrar.rollback()

    def _mark_rolled_back(self) -> None:
        """把没有失败或被阻断的记录标记为已关闭."""
        for record in self._ordered_records():
            if record.state not in (PluginState.FAILED, PluginState.BLOCKED):
                record.state = (
                    PluginState.FAILED
                    if self._has_cleanup_failure(record)
                    else PluginState.CLOSED
                )

    @staticmethod
    def _has_cleanup_failure(record: _PluginRecord) -> bool:
        return any(
            failure.phase in (PluginFailurePhase.CLEANING, PluginFailurePhase.STOPPING)
            for failure in record.failures
        )

    async def _run_callback(
        self,
        callback: object,
        *,
        name: str,
        timeout: float,
        scope: PluginScope,
    ) -> None:
        if not callable(callback) or not inspect.iscoroutinefunction(callback):
            raise TypeError("%s 必须是 async 函数" % name)
        result = callback()
        if not inspect.iscoroutine(result):
            raise TypeError("%s 必须返回 coroutine" % name)
        task = asyncio.create_task(result, name="butterbot.plugin.%s" % name)
        scope._track_task(task, report_failure=False)
        try:
            _, pending = await asyncio.wait((task,), timeout=timeout)
        except asyncio.CancelledError:
            task.cancel()
            raise
        if pending:
            task.cancel()
            raise TimeoutError("%s 执行超过 %.3f 秒" % (name, timeout))
        await task

    def _record_failure(
        self,
        plugin_id: str,
        phase: PluginFailurePhase,
        cause: BaseException,
    ) -> None:
        failure = PluginFailure(
            plugin_id=plugin_id,
            phase=phase,
            error_type=type(cause).__name__,
            timed_out=isinstance(cause, TimeoutError),
            cancelled=isinstance(cause, asyncio.CancelledError),
        )
        record = self._records[plugin_id]
        record.failures.append(failure)
        record.error = failure.error_type

    def _mark_failure(
        self,
        failed_id: str,
        phase: PluginFailurePhase,
        cause: BaseException,
    ) -> None:
        failed = self._records[failed_id]
        failed.state = PluginState.FAILED
        self._record_failure(failed_id, phase, cause)
        for record in self._ordered_records():
            if record.plugin_id == failed_id:
                continue
            if self._depends_on(record.plugin_id, failed_id):
                record.state = PluginState.BLOCKED
                record.error = "依赖插件 '%s' 失败" % failed_id

    def _depends_on(self, plugin_id: str, dependency_id: str) -> bool:
        pending = list(self._records[plugin_id].loaded.descriptor.requires_plugins)
        visited: set[str] = set()
        while pending:
            candidate = pending.pop()
            if candidate == dependency_id:
                return True
            if candidate in visited:
                continue
            visited.add(candidate)
            pending.extend(self._records[candidate].loaded.descriptor.requires_plugins)
        return False

    def _ordered_records(self) -> tuple[_PluginRecord, ...]:
        return tuple(self._records[plugin_id] for plugin_id in self.plugin_ids)


async def _run_bounded(
    coroutine: Coroutine[Any, Any, object],
    *,
    timeout: float,
    name: str,
) -> None:
    task = asyncio.create_task(coroutine, name=name)
    try:
        _, pending = await asyncio.wait((task,), timeout=timeout)
    except asyncio.CancelledError:
        task.cancel()
        task.add_done_callback(_consume_task_result)
        raise
    if pending:
        task.cancel()
        task.add_done_callback(_consume_task_result)
        raise TimeoutError("%s 执行超过 %.3f 秒" % (name, timeout))
    await task


def _consume_task_result(task: asyncio.Task[object]) -> None:
    if task.cancelled():
        return
    try:
        task.exception()
    except asyncio.CancelledError:
        pass


__all__ = [
    "PluginFailure",
    "PluginFailurePhase",
    "PluginManager",
    "PluginState",
    "PluginStatus",
]
