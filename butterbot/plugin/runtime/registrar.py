from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path
from types import MappingProxyType
from typing import Any, ParamSpec
from uuid import UUID

from butterbot.app.config import (
    BuilderRegistration,
    ConfigBuilder,
    ConfigBuilderRegistry,
)
from butterbot.app.source_factory import (
    FactoryRegistration,
    SourceFactory,
    SourceFactoryRegistry,
)
from butterbot.core.event import SubscriptionHandle
from butterbot.core.exceptions import LifecycleError, SourceError
from butterbot.core.source import BaseSourceT

from .extension import ExtensionRegistrar

_SourceP = ParamSpec("_SourceP")
_log = getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CleanupRegistration:
    """一次插件清理回调注册的收据."""

    _registrar: "PluginRegistrar" = field(repr=False)
    _token: object = field(repr=False)

    def unregister(self) -> bool:
        """在回调尚未执行时撤销注册."""
        return self._registrar._remove_cleanup(self._token)


@dataclass(frozen=True, slots=True)
class RegistrationReceipt:
    """一个插件跨配置和运行阶段的注册快照."""

    owner_id: str
    builders: tuple[BuilderRegistration, ...]
    factories: tuple[FactoryRegistration, ...]
    source_ids: tuple[UUID, ...]
    subscriptions: tuple[SubscriptionHandle, ...]
    cleanups: tuple[CleanupRegistration, ...]


class ConfigRegistrar:
    """插件配置阶段的 owner-aware、可回滚注册器."""

    def __init__(
        self,
        owner_id: str,
        builder_registry: ConfigBuilderRegistry,
        factory_registry: SourceFactoryRegistry,
        *,
        settings: Mapping[str, object] | None = None,
        resource_root: Path | None = None,
    ) -> None:
        _validate_owner(owner_id)
        self._owner_id = owner_id
        self._builder_registry = builder_registry
        self._factory_registry = factory_registry
        self._settings = (
            MappingProxyType({})
            if settings is None
            else MappingProxyType(dict(settings))
        )
        self._resource_root = resource_root
        self._builders: list[BuilderRegistration] = []
        self._factories: list[FactoryRegistration] = []
        self._undo: list[Callable[[], bool]] = []
        self._committed = False
        self._closed = False

    @property
    def owner_id(self) -> str:
        return self._owner_id

    @property
    def settings(self) -> Mapping[str, object]:
        """返回当前插件隔离且只读的配置 namespace."""
        return self._settings

    @property
    def resource_root(self) -> Path | None:
        """返回本地插件资源根；distribution 插件使用 importlib.resources."""
        return self._resource_root

    @property
    def builders(self) -> tuple[BuilderRegistration, ...]:
        return tuple(self._builders)

    @property
    def factories(self) -> tuple[FactoryRegistration, ...]:
        return tuple(self._factories)

    @property
    def committed(self) -> bool:
        return self._committed

    @property
    def closed(self) -> bool:
        return self._closed

    def _require_open(self) -> None:
        if self._closed:
            raise LifecycleError("ConfigRegistrar 已关闭")
        if self._committed:
            raise LifecycleError("ConfigRegistrar 已提交，不能继续注册")

    def register_builder(
        self,
        source_name: str,
        builder: ConfigBuilder,
    ) -> BuilderRegistration:
        """注册配置 builder；插件不能替换其他 owner 的名称."""
        self._require_open()
        registration = self._builder_registry.register(
            source_name,
            builder,
            owner_id=self._owner_id,
        )
        self._builders.append(registration)
        self._undo.append(registration.unregister)
        return registration

    def register_factory(
        self,
        source_name: str,
        factory: SourceFactory,
        *,
        factory_id: str | None = None,
    ) -> FactoryRegistration:
        """注册稳定 factory ID，不要求与 Python 类名相同."""
        self._require_open()
        registration = self._factory_registry.register(
            source_name,
            factory,
            factory_name=factory_id,
            owner_id=self._owner_id,
        )
        self._factories.append(registration)
        self._undo.append(registration.unregister)
        return registration

    def commit(self) -> None:
        self._require_open()
        self._committed = True

    def rollback(self) -> None:
        """逆序撤销配置阶段的全部注册；重复调用安全."""
        if self._closed:
            return
        for unregister in reversed(self._undo):
            unregister()
        self._undo.clear()
        self._builders.clear()
        self._factories.clear()
        self._closed = True


class PluginRegistrar(ExtensionRegistrar):
    """由 PluginManager 注入 owner 的运行阶段 registrar."""

    def __init__(
        self,
        app: Any,
        owner_id: str,
        *,
        drain_timeout: float = 5.0,
        report_failure: Callable[[str, BaseException], None] | None = None,
    ) -> None:
        super().__init__(app, owner_id, drain_timeout=drain_timeout)
        self._report_failure = report_failure
        self._cleanups: list[tuple[object, Callable[[], Awaitable[None] | None]]] = []
        self._cleanup_registrations: list[CleanupRegistration] = []

    @property
    def cleanups(self) -> tuple[CleanupRegistration, ...]:
        """返回当前仍登记的 close callback 收据快照."""
        return tuple(self._cleanup_registrations)

    def add_source(
        self,
        source_cls: Callable[_SourceP, BaseSourceT],
        *args: _SourceP.args,
        **kwargs: _SourceP.kwargs,
    ) -> BaseSourceT:
        """以当前插件 owner 注册 Source，不允许插件伪造 owner."""
        self._require_open()
        source = self._app._add_owned_source(
            self.owner_id,
            source_cls,
            *args,
            **kwargs,
        )
        self._source_ids.append(source.uuid)
        return source

    def adopt_source(self, source_id: UUID) -> None:
        """接管配置阶段由当前 owner factory 创建的 Source."""
        self._require_open()
        entry = next(
            (
                item
                for item in self._app.manager.source_catalog.by_owner(self.owner_id)
                if item.source_id == source_id
            ),
            None,
        )
        if entry is None:
            raise SourceError("Source %s 不属于插件 '%s'" % (source_id, self.owner_id))
        if source_id not in self._source_ids:
            self._source_ids.append(source_id)

    def on_close(
        self,
        callback: Callable[[], Awaitable[None] | None],
    ) -> CleanupRegistration:
        """登记插件关闭回调；普通异常只记录，取消在完成其余清理后传播."""
        self._require_open()
        if not callable(callback):
            raise TypeError("callback 必须可调用")
        token = object()
        self._cleanups.append((token, callback))
        registration = CleanupRegistration(self, token)
        self._cleanup_registrations.append(registration)
        return registration

    def _remove_cleanup(self, token: object) -> bool:
        for index, (candidate, _) in enumerate(self._cleanups):
            if candidate is token:
                self._cleanups.pop(index)
                self._cleanup_registrations = [
                    registration
                    for registration in self._cleanup_registrations
                    if registration._token is not token
                ]
                return True
        return False

    async def aclose(self) -> None:
        if self.closed:
            return

        # 先阻止当前插件产生新 Handler，再执行插件自定义清理。
        for handle in reversed(self._subscriptions):
            self._app.bus.remove_subscription(handle)
        self._subscriptions.clear()

        cancelled: asyncio.CancelledError | None = None
        for _, callback in reversed(self._cleanups):
            try:
                result = callback()
                if inspect.isawaitable(result):
                    await result
            except asyncio.CancelledError as exc:
                cancelled = cancelled or exc
            except Exception as exc:
                if self._report_failure is not None:
                    self._report_failure("cleaning", exc)
                _log.exception("插件 '%s' 的清理回调失败", self.owner_id)
        self._cleanups.clear()
        self._cleanup_registrations.clear()

        try:
            await super().aclose()
        except asyncio.CancelledError as exc:
            cancelled = cancelled or exc
        if cancelled is not None:
            raise cancelled


def make_receipt(
    config: ConfigRegistrar,
    runtime: PluginRegistrar,
) -> RegistrationReceipt:
    """生成只读跨阶段注册快照."""
    return RegistrationReceipt(
        owner_id=config.owner_id,
        builders=config.builders,
        factories=config.factories,
        source_ids=runtime.source_ids,
        subscriptions=runtime.subscriptions,
        cleanups=runtime.cleanups,
    )


def _validate_owner(owner_id: str) -> None:
    if not owner_id or owner_id != owner_id.strip():
        raise ValueError("owner_id 必须是非空且无首尾空白的字符串")


__all__ = [
    "CleanupRegistration",
    "ConfigRegistrar",
    "PluginRegistrar",
    "RegistrationReceipt",
]
