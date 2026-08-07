"""NapCat 消息段构造与发送数据测试。"""

import inspect
from dataclasses import dataclass
from typing import Any, cast, get_args

import pytest
from pydantic import ValidationError

from butterbot.sources.napcat.data import (
    MessageNode,
    MessageNodeData,
    NapcatMessage,
    NapcatMessageBuilder,
    TextData,
    TextNode,
)
from butterbot.sources.napcat.data import segment_data as segment


@dataclass(frozen=True)
class BuilderContract:
    """公开 builder 参数与内部消息段数据的映射契约。"""

    method_name: str
    node_type: type[MessageNode]
    data_type: type[MessageNodeData]
    call_kwargs: dict[str, Any]
    parameter_map: dict[str, str]
    expected_data: dict[str, Any]


BUILDER_CONTRACTS = [
    BuilderContract(
        "text",
        segment.TextNode,
        segment.TextData,
        {"text": "测试文本"},
        {"text": "text"},
        {"text": "测试文本"},
    ),
    BuilderContract(
        "at",
        segment.AtNode,
        segment.AtData,
        {"qq": 123456, "name": "测试用户"},
        {"qq": "qq", "name": "name"},
        {"qq": "123456", "name": "测试用户"},
    ),
    BuilderContract(
        "at_all",
        segment.AtNode,
        segment.AtData,
        {},
        {},
        {"qq": "all"},
    ),
    BuilderContract(
        "image",
        segment.ImageNode,
        segment.ImageData,
        {
            "file": "image.png",
            "image_type": "flash",
            "url": "https://example.com/image.png",
            "cache": 1,
            "proxy": 0,
            "timeout": 30,
        },
        {
            "file": "file",
            "image_type": "type",
            "url": "url",
            "cache": "cache",
            "proxy": "proxy",
            "timeout": "timeout",
        },
        {
            "file": "image.png",
            "type": "flash",
            "url": "https://example.com/image.png",
            "cache": 1,
            "proxy": 0,
            "timeout": 30,
        },
    ),
    BuilderContract(
        "reply",
        segment.ReplyNode,
        segment.ReplyData,
        {"message_id": 123, "seq": 456},
        {"message_id": "id", "seq": "seq"},
        {"id": "123", "seq": 456},
    ),
    BuilderContract(
        "face",
        segment.FaceNode,
        segment.FaceData,
        {"face_id": "14"},
        {"face_id": "id"},
        {"id": "14"},
    ),
    BuilderContract(
        "record",
        segment.RecordNode,
        segment.RecordData,
        {
            "file": "record.amr",
            "magic": 1,
            "url": "https://example.com/record.amr",
            "cache": 1,
            "proxy": 0,
            "timeout": 30,
        },
        {
            "file": "file",
            "magic": "magic",
            "url": "url",
            "cache": "cache",
            "proxy": "proxy",
            "timeout": "timeout",
        },
        {
            "file": "record.amr",
            "magic": 1,
            "url": "https://example.com/record.amr",
            "cache": 1,
            "proxy": 0,
            "timeout": 30,
        },
    ),
    BuilderContract(
        "video",
        segment.VideoNode,
        segment.VideoData,
        {
            "file": "video.mp4",
            "url": "https://example.com/video.mp4",
            "cache": 1,
            "proxy": 0,
            "timeout": 30,
        },
        {
            "file": "file",
            "url": "url",
            "cache": "cache",
            "proxy": "proxy",
            "timeout": "timeout",
        },
        {
            "file": "video.mp4",
            "url": "https://example.com/video.mp4",
            "cache": 1,
            "proxy": 0,
            "timeout": 30,
        },
    ),
    BuilderContract(
        "poke",
        segment.PokeNode,
        segment.PokeData,
        {"poke_type": "poke", "poke_id": 5, "name": "戳一戳"},
        {"poke_type": "type", "poke_id": "id", "name": "name"},
        {"type": "poke", "id": "5", "name": "戳一戳"},
    ),
    BuilderContract(
        "share",
        segment.ShareNode,
        segment.ShareData,
        {
            "url": "https://example.com",
            "title": "示例",
            "content": "说明",
            "image": "https://example.com/cover.png",
        },
        {"url": "url", "title": "title", "content": "content", "image": "image"},
        {
            "url": "https://example.com",
            "title": "示例",
            "content": "说明",
            "image": "https://example.com/cover.png",
        },
    ),
    BuilderContract(
        "contact",
        segment.ContactNode,
        segment.ContactData,
        {"contact_type": "group", "contact_id": 123456},
        {"contact_type": "type", "contact_id": "id"},
        {"type": "group", "id": "123456"},
    ),
    BuilderContract(
        "location",
        segment.LocationNode,
        segment.LocationData,
        {"lat": 1.5, "lon": 2.5, "title": "位置", "content": "说明"},
        {"lat": "lat", "lon": "lon", "title": "title", "content": "content"},
        {"lat": "1.5", "lon": "2.5", "title": "位置", "content": "说明"},
    ),
    BuilderContract(
        "music",
        segment.MusicNode,
        segment.MusicData,
        {
            "music_type": "custom",
            "music_id": "song-id",
            "url": "https://example.com/song",
            "audio": "https://example.com/song.mp3",
            "title": "歌曲",
            "content": "歌手",
            "image": "https://example.com/cover.png",
        },
        {
            "music_type": "type",
            "music_id": "id",
            "url": "url",
            "audio": "audio",
            "title": "title",
            "content": "content",
            "image": "image",
        },
        {
            "type": "custom",
            "id": "song-id",
            "url": "https://example.com/song",
            "audio": "https://example.com/song.mp3",
            "title": "歌曲",
            "content": "歌手",
            "image": "https://example.com/cover.png",
        },
    ),
    BuilderContract(
        "file",
        segment.FileNode,
        segment.FileData,
        {"file": "document.txt"},
        {"file": "file"},
        {"file": "document.txt"},
    ),
    BuilderContract(
        "anonymous",
        segment.AnonymousNode,
        segment.AnonymousData,
        {"ignore": 1},
        {"ignore": "ignore"},
        {"ignore": 1},
    ),
    BuilderContract("rps", segment.RpsNode, segment.RpsData, {}, {}, {}),
    BuilderContract("dice", segment.DiceNode, segment.DiceData, {}, {}, {}),
    BuilderContract("shake", segment.ShakeNode, segment.ShakeData, {}, {}, {}),
    BuilderContract(
        "xml",
        segment.XmlNode,
        segment.XmlData,
        {"data": "<msg />"},
        {"data": "data"},
        {"data": "<msg />"},
    ),
    BuilderContract(
        "json",
        segment.JsonNode,
        segment.JsonData,
        {"data": '{"message":"test"}'},
        {"data": "data"},
        {"data": '{"message":"test"}'},
    ),
]


def test_builder_contracts_cover_all_public_segment_methods() -> None:
    """每个公开消息段 builder 都必须维护参数映射契约。"""
    public_methods = {
        name
        for name, value in vars(NapcatMessageBuilder).items()
        if inspect.isfunction(value) and not name.startswith("_") and name != "build"
    }

    assert {contract.method_name for contract in BUILDER_CONTRACTS} == public_methods


@pytest.mark.parametrize(
    "contract",
    BUILDER_CONTRACTS,
    ids=lambda contract: contract.method_name,
)
def test_builder_contract(contract: BuilderContract) -> None:
    """公开参数应映射到对应 Data 字段并构造正确的 Node。"""
    method = getattr(NapcatMessageBuilder, contract.method_name)
    parameters = {
        name: parameter
        for name, parameter in inspect.signature(method).parameters.items()
        if name != "self"
    }
    assert all(
        parameter.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        for parameter in parameters.values()
    )
    assert set(parameters) == set(contract.parameter_map)

    data_fields = contract.data_type.model_fields
    assert issubclass(contract.data_type, MessageNodeData)
    assert set(contract.parameter_map.values()) <= set(data_fields)
    assert set(contract.expected_data) <= set(data_fields)
    assert {name for name, field in data_fields.items() if field.is_required()} <= set(
        contract.expected_data
    )

    node_data_annotation = contract.node_type.model_fields["data"].annotation
    assert contract.data_type in (
        node_data_annotation,
        *get_args(node_data_annotation),
    )

    builder = NapcatMessageBuilder()
    getattr(builder, contract.method_name)(**contract.call_kwargs)
    nodes = builder.build().message_list

    assert len(nodes) == 1
    assert type(nodes[0]) is contract.node_type
    node_data = cast(Any, nodes[0]).data
    assert type(node_data) is contract.data_type
    assert node_data == contract.data_type.model_validate(contract.expected_data)


class TestNapcatMessageBuilder:
    def test_builds_message_from_empty_instance(self) -> None:
        """空消息应能以链式调用追加消息段。"""
        message = (
            NapcatMessageBuilder()
            .at_all()
            .text("通知内容")
            .image("https://example.com/image.png")
        )

        assert message.build().to_list_dict() == [
            {"type": "at", "data": {"qq": "all"}},
            {"type": "text", "data": {"text": "通知内容"}},
            {
                "type": "image",
                "data": {"file": "https://example.com/image.png"},
            },
        ]

    def test_supports_all_segment_types_through_builder(self) -> None:
        """消息段应统一由建造器追加。"""
        message = (
            NapcatMessageBuilder()
            .at_all()
            .text("通知内容")
            .image("https://example.com/image.png")
        )

        assert message.build().to_list_dict() == [
            {"type": "at", "data": {"qq": "all"}},
            {"type": "text", "data": {"text": "通知内容"}},
            {
                "type": "image",
                "data": {"file": "https://example.com/image.png"},
            },
        ]

    def test_converts_numeric_identifiers_to_onebot_strings(self) -> None:
        """OneBot11 约定为字符串的标识符应由构造器统一转换。"""
        message = NapcatMessageBuilder().at(123456).reply(987654)

        assert message.build().to_list_dict() == [
            {"type": "at", "data": {"qq": "123456"}},
            {"type": "reply", "data": {"id": "987654"}},
        ]

    def test_concatenates_builders_with_add_and_and(self) -> None:
        """加号和与运算符均应拼接消息段且不修改原建造器。"""
        prefix = NapcatMessageBuilder().at_all()
        suffix = NapcatMessageBuilder().text("通知")

        added = prefix + suffix
        anded = prefix & suffix.build()

        assert prefix.build().to_list_dict() == [{"type": "at", "data": {"qq": "all"}}]
        assert (
            added.build().to_list_dict()
            == anded.build().to_list_dict()
            == [
                {"type": "at", "data": {"qq": "all"}},
                {"type": "text", "data": {"text": "通知"}},
            ]
        )

    @pytest.mark.parametrize("operator", ["+", "&"])
    def test_rejects_string_when_concatenating(self, operator: str) -> None:
        """字符串不能作为消息段与建造器拼接。"""
        builder = NapcatMessageBuilder().text("通知")
        value = cast(Any, "不是消息段")

        with pytest.raises(TypeError, match="合并非消息段内容"):
            if operator == "+":
                result = builder + value
            else:
                result = builder & value
            assert result is not None

    def test_revalidates_nodes_before_serializing(self) -> None:
        """发送数据导出前应重新校验每个消息段。"""
        message = NapcatMessage(
            [TextNode.model_construct(data=TextData.model_construct(text=None))]
        )

        with pytest.raises(ValidationError):
            message.to_list_dict()
