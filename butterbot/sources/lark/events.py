"""飞书事件的 ``Event[Data]`` 类型别名。"""

from typing import TypeAlias

from butterbot.core.event import Event

from .data import (
    LarkBotAddedData,
    LarkBotDeletedData,
    LarkBotP2pChatEnteredData,
    LarkChatDisbandedData,
    LarkChatUpdatedData,
    LarkData,
    LarkMenuData,
    LarkMessageReadData,
    LarkMessageRecalledData,
    LarkMessageReceiveData,
    LarkReactionCreatedData,
    LarkReactionDeletedData,
    LarkUnknownData,
    LarkUserAddedData,
    LarkUserDeletedData,
    LarkUserWithdrawnData,
)

LarkEvent: TypeAlias = Event[LarkData]
LarkUnknownEvent: TypeAlias = Event[LarkUnknownData]
LarkMessageReceiveEvent: TypeAlias = Event[LarkMessageReceiveData]
LarkMessageReadEvent: TypeAlias = Event[LarkMessageReadData]
LarkMessageRecalledEvent: TypeAlias = Event[LarkMessageRecalledData]
LarkReactionCreatedEvent: TypeAlias = Event[LarkReactionCreatedData]
LarkReactionDeletedEvent: TypeAlias = Event[LarkReactionDeletedData]
LarkChatUpdatedEvent: TypeAlias = Event[LarkChatUpdatedData]
LarkChatDisbandedEvent: TypeAlias = Event[LarkChatDisbandedData]
LarkBotP2pChatEnteredEvent: TypeAlias = Event[LarkBotP2pChatEnteredData]
LarkUserAddedEvent: TypeAlias = Event[LarkUserAddedData]
LarkUserDeletedEvent: TypeAlias = Event[LarkUserDeletedData]
LarkUserWithdrawnEvent: TypeAlias = Event[LarkUserWithdrawnData]
LarkBotAddedEvent: TypeAlias = Event[LarkBotAddedData]
LarkBotDeletedEvent: TypeAlias = Event[LarkBotDeletedData]
LarkMenuEvent: TypeAlias = Event[LarkMenuData]

__all__ = [
    "LarkBotAddedEvent",
    "LarkBotDeletedEvent",
    "LarkBotP2pChatEnteredEvent",
    "LarkChatDisbandedEvent",
    "LarkChatUpdatedEvent",
    "LarkEvent",
    "LarkMenuEvent",
    "LarkMessageReadEvent",
    "LarkMessageRecalledEvent",
    "LarkMessageReceiveEvent",
    "LarkReactionCreatedEvent",
    "LarkReactionDeletedEvent",
    "LarkUnknownEvent",
    "LarkUserAddedEvent",
    "LarkUserDeletedEvent",
    "LarkUserWithdrawnEvent",
]
