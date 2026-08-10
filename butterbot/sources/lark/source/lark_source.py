"""把飞书 WebSocket envelope 转换并发布为 ButterBot 事件。"""

from __future__ import annotations

import time
from collections import OrderedDict
from logging import getLogger
from typing import Any

from butterbot.core.event import Event
from butterbot.core.source import BaseSource
from butterbot.utils.websocket import (
    ConnectionError,
    ConnectionHealth,
    ConnectionHealthState,
)

from ..api import LarkApi
from ..data import LarkData
from ..types import LarkType

_log = getLogger("LarkSource")


class LarkSource(BaseSource):
    """使用飞书官方 WebSocket 长连接接收 v2.0 事件。"""

    supported_types = LarkType
    source_kind = "lark.events"
    config_key = "lark"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._seen_events: OrderedDict[str, float] = OrderedDict()

    async def on_start(self) -> None:
        """绑定事件与健康处理器，然后等待 WebSocket 首次就绪。"""
        self.api.set_handler(self._process_event)
        self.api.set_health_handler(self._handle_connection_health)
        await self.api.start()

    async def on_stop(self) -> None:
        """停止 WebSocket 并清空当前进程内的事件去重缓存。"""
        await self.api.stop()
        self._seen_events.clear()

    @property
    def api(self) -> LarkApi:
        """返回当前配置键对应的飞书 API 单例。"""
        return self.ctx.api_ctx.get(LarkApi, self.config_key)

    async def _process_event(self, payload: dict[str, Any]) -> None:
        try:
            data = LarkData.from_envelope(payload)
            if self._is_duplicate(data.header.event_id):
                _log.debug("忽略重复飞书事件: %s", data.header.event_id)
                return
            data.bind_runtime(self.ctx, self.config_key)
            await self.ctx.bus.publish(
                self.uuid,
                Event(data=data, status=data.event_type),
            )
        except Exception:
            _log.exception("解析或发布飞书事件失败: %s", payload)

    def _is_duplicate(self, event_id: str) -> bool:
        config = self.api.config
        if not config.deduplicate_events:
            return False

        now = time.monotonic()
        cutoff = now - config.dedup_ttl
        while self._seen_events:
            _, seen_at = next(iter(self._seen_events.items()))
            if seen_at >= cutoff:
                break
            self._seen_events.popitem(last=False)

        if event_id in self._seen_events:
            self._seen_events.move_to_end(event_id)
            return True
        self._seen_events[event_id] = now
        while len(self._seen_events) > config.dedup_max_entries:
            self._seen_events.popitem(last=False)
        return False

    def _handle_connection_health(self, health: ConnectionHealth) -> None:
        if health.state is ConnectionHealthState.READY:
            self._report_ready(at=health.last_success_at)
            return
        if (
            health.state
            in (ConnectionHealthState.DEGRADED, ConnectionHealthState.STOPPED)
            and self.running
        ):
            self._report_degraded(
                ConnectionError(
                    health.last_error_message or "飞书 WebSocket connection lost"
                )
            )
