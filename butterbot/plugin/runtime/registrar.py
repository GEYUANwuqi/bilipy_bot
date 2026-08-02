from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from logging import getLogger
from typing import Any

from butterbot.core.event import SubscriptionHandle

from ._transaction import _RuntimeRegistrationTransaction

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
    """插件行为注册的只读快照."""

    owner_id: str
    subscriptions: tuple[SubscriptionHandle, ...]
    cleanups: tuple[CleanupRegistration, ...]


class PluginRegistrar(_RuntimeRegistrationTransaction):
    """只管理 Handler 与插件自身非 Source 资源的运行阶段事务."""

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


def make_receipt(runtime: PluginRegistrar) -> RegistrationReceipt:
    """生成一个不包含 Source 所有权的行为注册快照."""
    return RegistrationReceipt(
        owner_id=runtime.owner_id,
        subscriptions=runtime.subscriptions,
        cleanups=runtime.cleanups,
    )


__all__ = [
    "CleanupRegistration",
    "PluginRegistrar",
    "RegistrationReceipt",
]
