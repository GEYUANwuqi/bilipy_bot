from typing import Any, Optional
from logging import getLogger

from .base_source import BaseSource
from napcat_data import (
    GroupMessageData,
    PrivateMessageData,
    NoticeEventData,
    RequestEventData,
    LifecycleEventData,
    HeartbeatEventData,
)
from napcat_data.dto import (
    GroupMessageDTO,
    PrivateMessageDTO,
    NoticeEventDTO,
    RequestEventDTO,
    HeartbeatEventDTO,
    LifecycleEventDTO,
)
from api import NapcatApi
from event import Event
from utils import NapcatType


_log = getLogger("NapcatSource")


class NapcatSource(BaseSource):
    """Napcat 事件源.

    使用ws协议连接napcat服务器，接收并发布事件。
    """

    def __init__(self):
        """初始化 Napcat 事件源."""
        super().__init__()

    async def _process_messages(self, message: dict[str, Any]) -> None:
        """处理接收到的消息."""
        napcat_type = NapcatType.get_type(message.get("post_type"))
        event: Optional[Event] = None
        if napcat_type.matches(NapcatType.MESSAGE):
            if message.get("message_type", "") == "group":
                message_data_dto = GroupMessageDTO.from_dict(message)
                message_data = GroupMessageData.from_dto(message_data_dto)
                event = Event(data = message_data, status = napcat_type)
            elif message.get("message_type", "") == "private":
                message_data_dto = PrivateMessageDTO.from_dict(message)
                message_data = PrivateMessageData.from_dto(message_data_dto)
                event = Event(data = message_data, status = napcat_type)
        elif napcat_type.matches(NapcatType.NOTICE):
            message_data_dto = NoticeEventDTO.from_dict(message)
            message_data = NoticeEventData.from_dto(message_data_dto)
            event = Event(data = message_data, status = napcat_type)
        elif napcat_type.matches(NapcatType.REQUEST):
            message_data_dto = RequestEventDTO.from_dict(message)
            message_data = RequestEventData.from_dto(message_data_dto)
            event = Event(data = message_data, status = napcat_type)
        elif napcat_type.matches(NapcatType.META):
            if message.get("meta_event_type", "") == "heartbeat":
                message_data_dto = HeartbeatEventDTO.from_dict(message)
                message_data = HeartbeatEventData.from_dto(message_data_dto)
                event = Event(data = message_data, status = napcat_type)
            elif message.get("meta_event_type", "") == "lifecycle":
                message_data_dto = LifecycleEventDTO.from_dict(message)
                message_data = LifecycleEventData.from_dto(message_data_dto)
                event = Event(data = message_data, status = napcat_type)
        else:
            _log.warning("未处理的消息类型: %s", napcat_type)

        if event is not None:
            await self.ctx.bus.publish(self.uuid, event)

    async def start(self) -> None:
        self.api.set_handler(self._process_messages)
        await self.api.start()

    async def stop(self) -> None:
        await self.api.stop()

    @property
    def api(self) -> NapcatApi:
        return self.ctx.api_ctx.get(NapcatApi)
