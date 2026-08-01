from logging import getLogger
from typing import Any

from butterbot.core.event import Event
from butterbot.core.source import BaseSource
from butterbot.utils import ConnectionHealth, ConnectionHealthState
from butterbot.utils.websocket import ConnectionError

from ..api import (
    NapcatApi,
)
from ..data import NapcatData
from ..types import (
    NapcatType,
)

_log = getLogger("NapcatSource")


class NapcatSource(BaseSource):
    """Napcat 事件源.

    使用ws协议连接napcat服务器，接收并发布事件。
    """

    supported_types = NapcatType
    source_kind = "napcat.events"
    config_key = "napcat"

    async def on_start(self) -> None:
        self.api.set_handler(self._process_messages)
        self.api.set_health_handler(self._handle_connection_health)
        await self.api.start()

    async def on_stop(self) -> None:
        await self.api.stop()

    def _handle_connection_health(self, health: ConnectionHealth) -> None:
        """把 WebSocket 的就绪/降级变化投影到 Source 健康快照."""
        if health.state is ConnectionHealthState.READY:
            self._report_ready(at=health.last_success_at)
            return
        if (
            health.state
            in (
                ConnectionHealthState.DEGRADED,
                ConnectionHealthState.STOPPED,
            )
            and self.running
        ):
            self._report_degraded(
                ConnectionError(
                    health.last_error_message or "NapCat WebSocket connection lost"
                )
            )

    async def _process_messages(self, message: dict[str, Any]) -> None:
        """处理接收到的消息."""
        event: Event[NapcatData] | None = None

        try:
            # 使用 BaseDataModel 的自动分发构造
            napcat_event = NapcatData.from_dict(message)
            # 状态由已完成 discriminator 分发的 Data 类型提供。
            # 这样生产路径不再同时维护一套 raw dict 分支路由。
            napcat_type = napcat_event.event_type

            if napcat_type.matches(NapcatType.ALL):
                event = Event(data=napcat_event, status=napcat_type)
            else:
                _log.warning("未处理的消息类型: %s", napcat_type)
        except Exception as e:
            _log.error("解析消息失败: %s, 原始消息: %s", e, message)
            return

        if event is not None:
            await self.ctx.bus.publish(self.uuid, event)

    @property
    def api(self) -> NapcatApi:
        return self.ctx.api_ctx.get(NapcatApi, self.config_key)
