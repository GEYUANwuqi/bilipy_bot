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
    """记录同一 owner 的 Handler 订阅并提供逆序清理."""

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
            config_key = (
                "<未指定>"
                if spec.source.config_key is None
                else repr(spec.source.config_key)
            )
            raise SourceError(
                "未找到插件订阅所需的事件源: "
                "source_kind=%r, config_key=%s; "
                "请检查 sources 配置和插件 config_key"
                % (
                    spec.source.source_kind,
                    config_key,
                )
            )
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

    def attach_subscription(
        self,
        spec: SubscriptionSpec,
        source_id: UUID,
    ) -> SubscriptionHandle:
        """为运行期新建 Source 追加一条已声明订阅."""
        if self._closed or not self._committed:
            raise LifecycleError("插件订阅尚未提交或已经关闭")
        source = self._app.get_source(source_id)
        if source is None:
            raise SourceError("运行期事件源不存在")
        handle = self._app.add_subscriber(
            source.uuid,
            spec.callback,
            spec.status,
            event_filter=spec.event_filter,
            owner_id=self._owner_id,
        )
        self._subscriptions.append(handle)
        return handle

    def detach_source(self, source_id: UUID) -> None:
        """撤销并遗忘指向一个运行期 Source 的全部订阅句柄."""
        retained: list[SubscriptionHandle] = []
        for handle in self._subscriptions:
            if handle.source_id == source_id:
                self._app.bus.remove_subscription(handle)
            else:
                retained.append(handle)
        self._subscriptions = retained

    def commit(self) -> None:
        """提交注册事务; 之后只能整体关闭."""
        self._require_open()
        self._committed = True

    async def aclose(self) -> None:
        """幂等退订并排空当前 owner 的回调."""
        if self._closed:
            return

        for handle in reversed(self._subscriptions):
            self._app.bus.remove_subscription(handle)
        self._subscriptions.clear()

        cancelled: asyncio.CancelledError | None = None
        errors: list[Exception] = []

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
            and self._app.bus.pending_callbacks_for(self._owner_id) == 0
        )
        if cancelled is not None:
            raise cancelled
        if errors:
            raise errors[0]


__all__ = ["_RuntimeRegistrationTransaction"]
