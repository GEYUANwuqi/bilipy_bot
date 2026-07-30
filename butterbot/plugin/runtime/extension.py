from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, ParamSpec
from uuid import UUID

from butterbot.core.event import SubscriptionHandle
from butterbot.core.exceptions import LifecycleError, SourceError
from butterbot.core.source import BaseSourceT
from butterbot.plugin.contracts.routing import SubscriptionSpec

if TYPE_CHECKING:
    from butterbot.app.bot_app import BotApp

_SourceP = ParamSpec("_SourceP")


class ExtensionRegistrar:
    """把一组 Source 和订阅作为同一所有者进行事务注册.

    该类只服务手工原型验证，不负责发现模块、解析依赖或加载不可信代码。
    注册阶段失败时，调用 :meth:`rollback` 可撤销已经产生的副作用。
    """

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
        """返回本次注册拥有的 Source UUID 快照."""
        return tuple(self._source_ids)

    @property
    def subscriptions(self) -> tuple[SubscriptionHandle, ...]:
        """返回本次注册拥有的订阅句柄快照."""
        return tuple(self._subscriptions)

    def _require_open(self) -> None:
        if self._closed:
            raise LifecycleError("ExtensionRegistrar 已关闭")
        if self._committed:
            raise LifecycleError("ExtensionRegistrar 已提交，不能继续注册")

    def add_source(
        self,
        source_cls: Callable[_SourceP, BaseSourceT],
        *args: _SourceP.args,
        **kwargs: _SourceP.kwargs,
    ) -> BaseSourceT:
        """注册并持有一个 Source，不自动启动."""
        self._require_open()
        source = self._app.add_source(source_cls, *args, **kwargs)
        self._source_ids.append(source.uuid)
        return source

    def add_subscription(
        self,
        spec: SubscriptionSpec,
    ) -> tuple[SubscriptionHandle, ...]:
        """解析 SourceRef 并注册订阅.

        默认要求逻辑引用唯一。只有显式设置 ``allow_multiple=True`` 时才会
        fan-out 到所有匹配实例；运行期后来新增的 Source 不会自动绑定。
        """
        self._require_open()
        sources = self._app.get_sources(spec.source)
        if not sources:
            raise SourceError("SourceRef %r 未匹配到事件源" % (spec.source,))
        if len(sources) > 1 and not spec.allow_multiple:
            raise SourceError(
                "SourceRef %r 匹配到 %s 个事件源；"
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
        """提交注册事务；之后只允许整体关闭."""
        self._require_open()
        self._committed = True

    async def rollback(self) -> None:
        """撤销本 registrar 拥有的注册项，已提交事务也可关闭."""
        await self.aclose()

    async def aclose(self) -> None:
        """幂等关闭：退订、移除 Source，并排空该 owner 的回调."""
        if self._closed:
            return

        for handle in reversed(self._subscriptions):
            self._app.bus.remove_subscription(handle)
        self._subscriptions.clear()

        cancelled: asyncio.CancelledError | None = None
        for source_id in reversed(self._source_ids):
            try:
                await self._app.remove_source(source_id)
            except asyncio.CancelledError as exc:
                cancelled = cancelled or exc
        self._source_ids.clear()

        try:
            await self._app.bus.drain_owner(
                self._owner_id,
                timeout=self._drain_timeout,
            )
        except asyncio.CancelledError as exc:
            cancelled = cancelled or exc

        self._closed = (
            not self._subscriptions
            and not self._source_ids
            and self._app.bus.pending_callbacks_for(self._owner_id) == 0
        )
        if cancelled is not None:
            raise cancelled

    async def __aenter__(self) -> ExtensionRegistrar:
        self._require_open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        if exc_type is None:
            self.commit()
        else:
            await self.rollback()


__all__ = ["ExtensionRegistrar"]
