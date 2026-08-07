"""NapCat 可发送合并转发消息模型与建造器。"""

from collections.abc import Iterator
from typing import Self

from butterbot.core.data import AutoDispatchList

from .segment_data import (
    ForwardNodeNode,
    NapcatMessage,
    NapcatMessageBuilder,
)


class NapcatForwardMessage(AutoDispatchList[ForwardNodeNode]):
    """仅包含可发送合并转发节点的消息。"""

    @classmethod
    def element_type(cls) -> type[ForwardNodeNode]:
        return ForwardNodeNode

    def __iter__(self) -> Iterator[ForwardNodeNode]:
        return iter(self.root)

    def to_list_dict(self) -> list[dict]:
        """校验并导出 NapCat ``send_forward_msg`` 所需节点列表。"""
        return [
            type(node)
            .model_validate(node.model_dump(mode="python"))
            .model_dump(mode="json", exclude_none=True)
            for node in self
        ]


class NapcatForwardMessageBuilder:
    """用于构造可发送合并转发消息的建造器。"""

    def __init__(
        self,
        user_id: str | int | None = None,
        nickname: str | None = None,
    ) -> None:
        self._user_id = None if user_id is None else str(user_id)
        self._nickname = nickname
        self._nodes: list[ForwardNodeNode] = []

    def set_author(self, user_id: str | int, nickname: str) -> Self:
        """设置后续自定义节点默认使用的作者。"""
        self._user_id = str(user_id)
        self._nickname = nickname
        return self

    def forward(self, message_id: str | int) -> Self:
        """追加一个引用已有消息的转发节点。"""
        self._nodes.append(ForwardNodeNode.build(id=str(message_id)))
        return self

    def node(
        self,
        content: NapcatMessage | NapcatMessageBuilder,
        *,
        user_id: str | int | None = None,
        nickname: str | None = None,
        prompt: str | None = None,
        summary: str | None = None,
        source: str | None = None,
    ) -> Self:
        """追加一个包含普通消息段的自定义转发节点。"""
        resolved_user_id = self._user_id if user_id is None else str(user_id)
        resolved_nickname = self._nickname if nickname is None else nickname
        if resolved_user_id is None or resolved_nickname is None:
            raise ValueError("自定义转发节点必须提供 user_id 和 nickname")

        if isinstance(content, NapcatMessageBuilder):
            content = content.build()
        self._nodes.append(
            ForwardNodeNode.build(
                user_id=resolved_user_id,
                nickname=resolved_nickname,
                content=content.to_list_dict(),
                prompt=prompt,
                summary=summary,
                source=source,
            )
        )
        return self

    def build(self) -> NapcatForwardMessage:
        """构造独立的可发送合并转发消息。"""
        return NapcatForwardMessage(list(self._nodes))
