"""插件运行时注册的私有事务实现."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from butterbot.core.event import SubscriptionHandle
from butterbot.core.exceptions import LifecycleError, SourceError
from butterbot.plugin.contracts.routing import SubscriptionSpec

if TYPE_CHECKING:
    from butterbot.app.bot_app import BotApp


class _RuntimeRegistrationTransaction:
    """记录同一 owner 的 Source 和订阅, 并提供逆序清理."""

    def __init__(
        self,
        app: BotApp,
        owner_id: str,
        *,
        drain_timeout: float = 5.0,
    ) -> None:
        if not owner_id or owner_id != owner_id.strip():
            raise ValueError("owner_id 必须是非空且无首尾空白的字符串")
        if drain_timeout < 0:
            raise ValueError("drain_timeout 不能小于 0")

        self._app = app
        self._owner_id = owner_id
        self._drain_timeout = drain_timeout
        self._source_ids: list[UUID] = []
        self._subscriptions: list[SubscriptionHandle] = []
        self._committed = False
        self._closed = False

    @property
    def owner_id(self) -> str:
        return self._owner_id

    @property
    def committed(self) -> bool:
        return self._committed

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def source_ids(self) -> tuple[UUID, ...]:
        """返回当前事务仍持有的 Source UUID."""
        return tuple(self._source_ids)

    @property
    def subscriptions(self) -> tuple[SubscriptionHandle, ...]:
        """返回当前事务仍持有的订阅句柄."""
        return tuple(self._subscriptions)

    def _require_open(self) -> None:
        if self._closed:
            raise LifecycleError("运行时注册事务已关闭")
        if self._committed:
            raise LifecycleError("运行时注册事务已提交, 不能继续注册")

    def add_subscription(
        self,
        spec: SubscriptionSpec,
    ) -> tuple[SubscriptionHandle, ...]:
        """解析 SourceRef 并原子记录本次 fan-out 的订阅."""
        self._require_open()
        sources = self._app.get_sources(spec.source)
        if not sources:
            raise SourceError("SourceRef %r 未匹配到事件源" % (spec.source,))
        if len(sources) > 1 and not spec.allow_multiple:
            raise SourceError(
                "SourceRef %r 匹配到 %s 个事件源; "
                "请指定 config_key 或显式启用 allow_multiple"
                % (spec.source, len(sources))
            )

        created: list[SubscriptionHandle] = []
        try:
            for source in sources:
                handle = self._app.add_subscriber(
                    source.uuid,
                    spec.callback,
                    spec.status,
                    event_filter=spec.event_filter,
                    owner_id=self._owner_id,
                )
                created.append(handle)
                self._subscriptions.append(handle)
        except BaseException:
            for handle in reversed(created):
                self._app.bus.remove_subscription(handle)
                self._subscriptions.remove(handle)
            raise
        return tuple(created)

    def commit(self) -> None:
        """提交注册事务; 之后只能整体关闭."""
        self._require_open()
        self._committed = True

    async def aclose(self) -> None:
        """幂等退订、移除 Source, 并排空当前 owner 的回调."""
        if self._closed:
            return

        for handle in reversed(self._subscriptions):
            self._app.bus.remove_subscription(handle)
        self._subscriptions.clear()

        cancelled: asyncio.CancelledError | None = None
        errors: list[Exception] = []
        for source_id in reversed(self._source_ids):
            try:
                await self._app.remove_source(source_id)
            except asyncio.CancelledError as exc:
                cancelled = cancelled or exc
            except Exception as exc:
                errors.append(exc)
            else:
                self._source_ids.remove(source_id)

        try:
            await self._app.bus.drain_owner(
                self._owner_id,
                timeout=self._drain_timeout,
            )
        except asyncio.CancelledError as exc:
            cancelled = cancelled or exc
        except Exception as exc:
            errors.append(exc)

        self._closed = (
            not self._subscriptions
            and not self._source_ids
            and self._app.bus.pending_callbacks_for(self._owner_id) == 0
        )
        if cancelled is not None:
            raise cancelled
        if errors:
            raise errors[0]


__all__ = ["_RuntimeRegistrationTransaction"]
