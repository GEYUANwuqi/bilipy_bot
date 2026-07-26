from logging import getLogger
from typing import Any

from butter_bot.core.event import Event
from butter_bot.core.source import BaseSource

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
    config_key = "napcat"

    async def on_start(self) -> None:
        self.api.set_handler(self._process_messages)
        await self.api.start()

    async def on_stop(self) -> None:
        await self.api.stop()

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
