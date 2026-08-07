"""NapCat 可发送合并转发消息测试。"""

import inspect
from typing import Any, cast

import pytest
from pydantic import ValidationError

from butterbot.sources.napcat.data import (
    ForwardNodeData,
    ForwardNodeNode,
    NapcatForwardMessage,
    NapcatForwardMessageBuilder,
    NapcatMessageBuilder,
    TextNode,
)


def test_forward_builder_methods_have_explicit_data_mapping() -> None:
    """转发 builder 应使用明确签名并维护公开参数到 Data 字段的映射。"""
    parameter_maps = {
        "forward": {"message_id": "id"},
        "node": {
            "content": "content",
            "user_id": "user_id",
            "nickname": "nickname",
            "prompt": "prompt",
            "summary": "summary",
            "source": "source",
        },
    }

    for method_name, parameter_map in parameter_maps.items():
        parameters = {
            name: parameter
            for name, parameter in inspect.signature(
                getattr(NapcatForwardMessageBuilder, method_name)
            ).parameters.items()
            if name != "self"
        }
        assert all(
            parameter.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            for parameter in parameters.values()
        )
        assert set(parameters) == set(parameter_map)
        assert set(parameter_map.values()) <= set(ForwardNodeData.model_fields)


def test_builds_reference_and_custom_forward_nodes() -> None:
    """引用节点和自定义节点应构造为独立的可发送转发消息。"""
    message = (
        NapcatForwardMessageBuilder(user_id=123456, nickname="默认作者")
        .forward(10001)
        .node(
            NapcatMessageBuilder().text("正文").image("image.png"),
            prompt="提示",
            summary="摘要",
            source="来源",
        )
        .build()
    )

    assert isinstance(message, NapcatForwardMessage)
    assert all(type(node) is ForwardNodeNode for node in message.root)
    assert message.to_list_dict() == [
        {"type": "node", "data": {"id": "10001"}},
        {
            "type": "node",
            "data": {
                "user_id": "123456",
                "nickname": "默认作者",
                "content": [
                    {"type": "text", "data": {"text": "正文"}},
                    {"type": "image", "data": {"file": "image.png"}},
                ],
                "prompt": "提示",
                "summary": "摘要",
                "source": "来源",
            },
        },
    ]


def test_set_author_and_node_override_are_chainable() -> None:
    """默认作者可链式更新，单个节点也可覆盖作者。"""
    builder = NapcatForwardMessageBuilder().set_author(1, "默认作者")
    builder.node(
        NapcatMessageBuilder().text("正文").build(),
        user_id=2,
        nickname="覆盖作者",
    )

    assert builder.build().to_list_dict() == [
        {
            "type": "node",
            "data": {
                "user_id": "2",
                "nickname": "覆盖作者",
                "content": [{"type": "text", "data": {"text": "正文"}}],
            },
        }
    ]


def test_custom_node_requires_author() -> None:
    """自定义节点缺少作者时应在构造边界失败。"""
    with pytest.raises(ValueError, match="必须提供 user_id 和 nickname"):
        NapcatForwardMessageBuilder().node(NapcatMessageBuilder().text("正文"))


def test_build_returns_independent_forward_message() -> None:
    """已构造的转发消息不应随 builder 后续追加而变化。"""
    builder = NapcatForwardMessageBuilder().forward(1)
    first = builder.build()
    builder.forward(2)

    assert first.to_list_dict() == [{"type": "node", "data": {"id": "1"}}]
    assert len(builder.build().root) == 2


def test_forward_message_rejects_regular_message_nodes() -> None:
    """转发消息根列表只能包含转发节点。"""
    nodes = cast(Any, [TextNode.build(text="不能直接放入")])

    with pytest.raises(ValidationError):
        NapcatForwardMessage(nodes)
