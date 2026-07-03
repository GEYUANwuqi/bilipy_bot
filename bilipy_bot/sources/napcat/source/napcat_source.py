from logging import getLogger
from typing import Any

from bilipy_bot.core.event import Event
from bilipy_bot.core.source import BaseSource

from ..api import (
    NapcatApi,
)
from ..data import NapcatEvent
from ..types import (
    NapcatType,
)

_log = getLogger("NapcatSource")


class NapcatSource(BaseSource):
    """Napcat 事件源.

    使用ws协议连接napcat服务器，接收并发布事件。
    """

    supported_types = NapcatType

    def __init__(self, config_key: str = "napcat"):
        """初始化 Napcat 事件源.
        Args:
            config_key: 配置键，默认"napcat"
        """
        super().__init__()
        self.config_key = config_key

    async def _process_messages(self, message: dict[str, Any]) -> None:
        """处理接收到的消息."""
        napcat_type = NapcatType.get_specific_type(message)
        event: Event | None = None

        try:
            # 使用 BaseDataModel 的自动分发构造
            napcat_event = NapcatEvent.from_dict(message)

            if napcat_type.matches(NapcatType.ALL):
                event = Event(data=napcat_event, status=napcat_type)
            else:
                _log.warning("未处理的消息类型: %s", napcat_type)
        except Exception as e:
            _log.error("解析消息失败: %s, 原始消息: %s", e, message)
            return

        if event is not None:
            await self.ctx.bus.publish(self.uuid, event)

    async def start(self) -> None:
        self.api.set_handler(self._process_messages)
        await self.api.start()

    async def stop(self) -> None:
        await self.api.stop()

    @property
    def api(self) -> NapcatApi:
        return self.ctx.api_ctx.get(NapcatApi, self.config_key)
