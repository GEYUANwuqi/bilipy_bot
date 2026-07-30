from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from logging import getLogger
from typing import TYPE_CHECKING

from butterbot.core.exceptions import LifecycleError
from butterbot.plugin.discovery.catalog import LoadedPlugin, PluginCatalog
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


@dataclass(frozen=True, slots=True)
class PluginStatus:
    """不包含配置值和 secret 的插件诊断快照."""

    plugin_id: str
    version: str
    state: PluginState
    origin_kind: str
    origin: str
    fingerprint: str | None
    error: str | None = None


@dataclass(slots=True)
class _PluginRecord:
    loaded: LoadedPlugin
    state: PluginState = PluginState.VALIDATED
    error: str | None = None

    @property
    def plugin_id(self) -> str:
        return self.loaded.descriptor.plugin_id


class PluginManager:
    """编排可信启动期插件的配置、注册、启动标记和逆序清理."""

    def __init__(
        self,
        catalog: PluginCatalog,
        builder_registry: "ConfigBuilderRegistry",
        factory_registry: "SourceFactoryRegistry",
        *,
        plugin_settings: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        self._catalog = catalog
        self._builder_registry = builder_registry
        self._factory_registry = factory_registry
        self._plugin_settings = plugin_settings or {}
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
                version=record.loaded.descriptor.version,
                state=record.state,
                origin_kind=record.loaded.origin.kind,
                origin=record.loaded.origin.location,
                fingerprint=record.loaded.origin.fingerprint,
                error=record.error,
            )
            for record in self._ordered_records()
        )

    @property
    def receipts(self) -> tuple[RegistrationReceipt, ...]:
        receipts: list[RegistrationReceipt] = []
        for plugin_id in self.plugin_ids:
            if self._records[plugin_id].state not in (
                PluginState.REGISTERED,
                PluginState.STARTED,
            ):
                continue
            config = self._config_registrars.get(plugin_id)
            runtime = self._runtime_registrars.get(plugin_id)
            if config is not None and runtime is not None:
                receipts.append(make_receipt(config, runtime))
        return tuple(receipts)

    def configure(self) -> None:
        """按依赖顺序执行无运行时副作用的配置 hook."""
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
                result = record.loaded.hooks.register_config(registrar)
                if inspect.isawaitable(result):
                    if inspect.iscoroutine(result):
                        result.close()
                    raise TypeError("register_config 必须是同步函数")
                registrar.commit()
            except BaseException as exc:
                registrar.rollback()
                self._mark_failure(plugin_id, exc)
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
                loaded = self._records[plugin_id].loaded
                registrar = PluginRegistrar(
                    app,
                    plugin_id,
                    settings=self._plugin_settings.get(plugin_id),
                    resource_root=loaded.origin.resource_root,
                )
                self._runtime_registrars[plugin_id] = registrar
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
        """按依赖顺序执行运行阶段 hook，失败时回滚本轮全部注册."""
        if self._closed:
            raise LifecycleError("PluginManager 已关闭")
        if self._registered:
            return
        if self._app is None:
            raise LifecycleError("PluginManager 尚未绑定应用")

        for record in self._ordered_records():
            plugin_id = record.plugin_id
            registrar = self._runtime_registrars[plugin_id]
            record.state = PluginState.REGISTERING
            try:
                result = record.loaded.hooks.register(registrar)
                if not inspect.isawaitable(result):
                    raise TypeError("register 必须是 async 函数")
                await result
                registrar.commit()
            except BaseException as exc:
                self._mark_failure(plugin_id, exc)
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
        """Source 全部启动成功后按依赖顺序执行插件启动 hook."""
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
                result = record.loaded.hooks.on_start()
                if not inspect.isawaitable(result):
                    raise TypeError("on_start 必须是 async 函数")
                await result
            except BaseException as exc:
                stop_cancelled = await self._run_stop_hooks(
                    tuple(reversed((*started_ids, plugin_id)))
                )
                self._mark_failure(plugin_id, exc)
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
        """在 Source 停止前按依赖逆序执行已启动插件的停止 hook."""
        if self._closed:
            return
        started_ids = tuple(
            record.plugin_id
            for record in reversed(self._ordered_records())
            if record.state == PluginState.STARTED
        )
        cancelled = await self._run_stop_hooks(started_ids)
        if cancelled is not None:
            raise cancelled

    async def fail_start(self, cause: BaseException) -> None:
        """Source 启动失败时撤销所有插件注册."""
        for record in self._ordered_records():
            if record.state in (PluginState.REGISTERED, PluginState.STARTED):
                record.state = PluginState.FAILED
                record.error = "Source 启动失败（%s）" % type(cause).__name__
        cleanup_cancelled = await self._rollback_all()
        if cleanup_cancelled is not None:
            raise cleanup_cancelled

    async def aclose(self) -> None:
        """按依赖逆序关闭插件，并撤销配置 registry."""
        if self._closed:
            return
        cancelled = await self._run_stop_hooks(
            tuple(
                record.plugin_id
                for record in reversed(self._ordered_records())
                if record.state == PluginState.STARTED
            )
        )
        runtime_cancelled = await self._close_runtime()
        cancelled = cancelled or runtime_cancelled
        self._rollback_config()
        self._closed = True
        for record in self._ordered_records():
            if record.state not in (PluginState.FAILED, PluginState.BLOCKED):
                record.state = PluginState.CLOSED
        if cancelled is not None:
            raise cancelled

    async def _run_stop_hooks(
        self,
        plugin_ids: tuple[str, ...],
    ) -> asyncio.CancelledError | None:
        cancelled: asyncio.CancelledError | None = None
        for plugin_id in plugin_ids:
            record = self._records[plugin_id]
            try:
                result = record.loaded.hooks.on_stop()
                if not inspect.isawaitable(result):
                    raise TypeError("on_stop 必须是 async 函数")
                await result
            except asyncio.CancelledError as exc:
                cancelled = cancelled or exc
            except Exception:
                _log.exception("插件 '%s' 的 on_stop 回调失败", plugin_id)
            if record.state == PluginState.STARTED:
                record.state = PluginState.REGISTERED
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
            registrar = self._runtime_registrars.get(plugin_id)
            if registrar is None:
                continue
            try:
                await registrar.aclose()
            except asyncio.CancelledError as exc:
                cancelled = cancelled or exc
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
                record.state = PluginState.CLOSED

    def _mark_failure(self, failed_id: str, cause: BaseException) -> None:
        failed = self._records[failed_id]
        failed.state = PluginState.FAILED
        failed.error = type(cause).__name__
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


__all__ = [
    "PluginManager",
    "PluginState",
    "PluginStatus",
]
