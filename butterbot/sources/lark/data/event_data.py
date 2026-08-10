"""飞书 v2.0 常用事件的领域数据模型与运行时便捷方法。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import Field, PrivateAttr

from butterbot.core.data import BaseDataModel

from ..types import LarkType

if TYPE_CHECKING:
    from butterbot.core.context import AppContext
    from butterbot.core.event import EventBus

    from ..api import LarkApi


class LarkEventHeader(BaseDataModel):
    event_id: str
    event_type: str
    create_time: str
    tenant_key: str | None = None
    app_id: str | None = None


class LarkUserId(BaseDataModel):
    user_id: str | None = None
    open_id: str | None = None
    union_id: str | None = None


class LarkSender(BaseDataModel):
    sender_id: LarkUserId
    sender_type: str
    tenant_key: str | None = None


class LarkMention(BaseDataModel):
    key: str
    id: LarkUserId
    mentioned_type: str | None = None
    name: str | None = None
    tenant_key: str | None = None


class LarkMessage(BaseDataModel):
    message_id: str
    root_id: str | None = None
    parent_id: str | None = None
    thread_id: str | None = None
    create_time: int | None = None
    update_time: int | None = None
    chat_id: str
    chat_type: str
    message_type: str
    content: str
    mentions: list[LarkMention] = Field(default_factory=list)

    @property
    def content_data(self) -> dict[str, Any]:
        """把飞书消息的 JSON 字符串内容解析为字典。"""
        try:
            value = json.loads(self.content)
        except (json.JSONDecodeError, TypeError):
            return {"text": self.content}
        return value if isinstance(value, dict) else {"value": value}

    @property
    def text(self) -> str:
        """返回文本消息正文；非文本消息没有 text 字段时返回空字符串。"""
        text = self.content_data.get("text", "")
        return text if isinstance(text, str) else str(text)


class LarkData(BaseDataModel):
    """飞书 v2.0 事件数据基类。"""

    discriminator_field: ClassVar[str] = "event_type"
    event_type: ClassVar[LarkType] = LarkType.UNKNOWN

    header: LarkEventHeader
    raw_data: dict[str, Any]

    _runtime: AppContext | None = PrivateAttr(default=None)
    _config_key: str | None = PrivateAttr(default=None)

    @classmethod
    def from_envelope(cls, raw: dict[str, Any]) -> LarkData:
        """把飞书标准 envelope 展平后按 ``header.event_type`` 分发。"""
        header = raw.get("header")
        event = raw.get("event")
        if not isinstance(header, dict) or not isinstance(event, dict):
            raise ValueError("飞书事件缺少 header 或 event")
        event_name = header.get("event_type")
        if not isinstance(event_name, str) or not event_name:
            raise ValueError("飞书事件缺少 header.event_type")

        normalized = dict(event)
        normalized.update(
            event_type=event_name,
            event_type_name=event_name,
            header=header,
            raw_data=raw,
        )
        if event_name not in cls._registry:
            return LarkUnknownData.model_validate(normalized)
        return cls.from_dict(normalized)

    def bind_runtime(self, runtime: AppContext, config_key: str) -> None:
        """绑定产生当前事件的应用上下文和飞书配置键。"""
        object.__setattr__(self, "_runtime", runtime)
        object.__setattr__(self, "_config_key", config_key)

    @property
    def runtime(self) -> AppContext:
        """返回 Source 发布事件时绑定的应用上下文。"""
        if self._runtime is None:
            raise RuntimeError("LarkData 尚未绑定 runtime")
        return self._runtime

    @property
    def config_key(self) -> str:
        """返回产生当前事件的飞书账号配置键。"""
        if self._config_key is None:
            raise RuntimeError("LarkData 尚未绑定 config_key")
        return self._config_key

    @property
    def bus(self) -> EventBus:
        """返回当前应用的事件总线。"""
        return self.runtime.bus

    @property
    def api(self) -> LarkApi:
        """返回与当前事件属于同一飞书账号的 API 实例。"""
        from ..api import LarkApi

        return self.runtime.api_ctx.get(LarkApi, self.config_key)


class LarkUnknownData(LarkData):
    """通过 ``custom_event_types`` 接收但尚无专用模型的事件。"""

    event_type: ClassVar[LarkType] = LarkType.UNKNOWN
    event_type_name: str


class LarkMessageReceiveData(LarkData):
    discriminator_value: ClassVar[str] = "im.message.receive_v1"
    event_type: ClassVar[LarkType] = LarkType.MESSAGE_RECEIVE

    sender: LarkSender
    message: LarkMessage

    async def reply(
        self,
        msg_type: str,
        content: str | dict[str, Any],
        *,
        reply_in_thread: bool = False,
    ) -> dict[str, Any]:
        """按指定消息类型引用回复当前消息。"""
        return await self.api.reply_message(
            self.message.message_id,
            msg_type,
            content,
            reply_in_thread=reply_in_thread,
        )

    async def reply_text(
        self,
        text: str,
        *,
        reply_in_thread: bool = False,
    ) -> dict[str, Any]:
        """引用回复当前消息；可选择在话题内回复。"""
        return await self.api.reply_text(
            self.message.message_id,
            text,
            reply_in_thread=reply_in_thread,
        )

    async def send_text(self, text: str) -> dict[str, Any]:
        """向当前消息所在会话发送一条不带引用的文本消息。"""
        return await self.api.send_text(self.message.chat_id, text)


class LarkReader(BaseDataModel):
    reader_id: LarkUserId
    read_time: str
    tenant_key: str | None = None


class LarkMessageReadData(LarkData):
    discriminator_value: ClassVar[str] = "im.message.message_read_v1"
    event_type: ClassVar[LarkType] = LarkType.MESSAGE_READ

    reader: LarkReader
    message_id_list: list[str]


class LarkMessageRecalledData(LarkData):
    discriminator_value: ClassVar[str] = "im.message.recalled_v1"
    event_type: ClassVar[LarkType] = LarkType.MESSAGE_RECALLED

    message_id: str
    chat_id: str
    recall_time: str
    recall_type: str


class LarkReactionType(BaseDataModel):
    emoji_type: str


class LarkReactionData(LarkData):
    message_id: str
    reaction_type: LarkReactionType
    operator_type: str
    user_id: LarkUserId | None = None
    app_id: str | None = None
    action_time: str


class LarkReactionCreatedData(LarkReactionData):
    discriminator_value: ClassVar[str] = "im.message.reaction.created_v1"
    event_type: ClassVar[LarkType] = LarkType.REACTION_CREATED


class LarkReactionDeletedData(LarkReactionData):
    discriminator_value: ClassVar[str] = "im.message.reaction.deleted_v1"
    event_type: ClassVar[LarkType] = LarkType.REACTION_DELETED


class LarkChatData(LarkData):
    chat_id: str
    operator_id: LarkUserId | None = None


class LarkChatUpdatedData(LarkChatData):
    discriminator_value: ClassVar[str] = "im.chat.updated_v1"
    event_type: ClassVar[LarkType] = LarkType.CHAT_UPDATED

    external: bool | None = None
    operator_tenant_key: str | None = None
    before_change: dict[str, Any] | None = None
    after_change: dict[str, Any] | None = None
    moderator_list: dict[str, Any] | None = None


class LarkChatDisbandedData(LarkChatData):
    discriminator_value: ClassVar[str] = "im.chat.disbanded_v1"
    event_type: ClassVar[LarkType] = LarkType.CHAT_DISBANDED

    external: bool | None = None
    operator_tenant_key: str | None = None
    name: str | None = None


class LarkBotP2pChatEnteredData(LarkChatData):
    discriminator_value: ClassVar[str] = "im.chat.access_event.bot_p2p_chat_entered_v1"
    event_type: ClassVar[LarkType] = LarkType.BOT_P2P_CHAT_ENTERED

    last_message_id: str | None = None
    last_message_create_time: str | None = None


class LarkChatMember(BaseDataModel):
    name: str | None = None
    tenant_key: str | None = None
    user_id: LarkUserId


class LarkMemberData(LarkChatData):
    external: bool | None = None
    operator_tenant_key: str | None = None
    name: str | None = None


class LarkUserMemberData(LarkMemberData):
    users: list[LarkChatMember]


class LarkUserAddedData(LarkUserMemberData):
    discriminator_value: ClassVar[str] = "im.chat.member.user.added_v1"
    event_type: ClassVar[LarkType] = LarkType.USER_ADDED


class LarkUserDeletedData(LarkUserMemberData):
    discriminator_value: ClassVar[str] = "im.chat.member.user.deleted_v1"
    event_type: ClassVar[LarkType] = LarkType.USER_DELETED


class LarkUserWithdrawnData(LarkUserMemberData):
    discriminator_value: ClassVar[str] = "im.chat.member.user.withdrawn_v1"
    event_type: ClassVar[LarkType] = LarkType.USER_WITHDRAWN


class LarkBotAddedData(LarkMemberData):
    discriminator_value: ClassVar[str] = "im.chat.member.bot.added_v1"
    event_type: ClassVar[LarkType] = LarkType.BOT_ADDED


class LarkBotDeletedData(LarkMemberData):
    discriminator_value: ClassVar[str] = "im.chat.member.bot.deleted_v1"
    event_type: ClassVar[LarkType] = LarkType.BOT_DELETED


class LarkMenuOperator(BaseDataModel):
    operator_name: str | None = None
    operator_id: LarkUserId


class LarkMenuData(LarkData):
    discriminator_value: ClassVar[str] = "application.bot.menu_v6"
    event_type: ClassVar[LarkType] = LarkType.MENU

    operator: LarkMenuOperator
    event_key: str
    timestamp: int
