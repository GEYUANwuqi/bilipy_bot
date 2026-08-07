"""
NapCat OneBot11 消息段数据模型

基于 OneBot11 协议定义的消息段类型，使用 BaseDataModel 实现自动分发构造
"""

from types import NotImplementedType
from typing import Any, ClassVar, Self, TypeVar, get_args

from butterbot.core.data import AutoDispatchList, BaseDataModel

# ==================== 嵌套数据类 ====================


class MessageNodeData(BaseDataModel):
    """消息段嵌套数据基类。"""


class TextData(MessageNodeData):
    """纯文本消息数据"""

    text: str


class FaceData(MessageNodeData):
    """QQ表情消息数据"""

    id: str


class ImageData(MessageNodeData):
    """图片消息数据"""

    file: str
    type: str | None = None  # 'flash' 表示闪照
    url: str | None = None
    cache: int | None = None  # 0 或 1
    proxy: int | None = None  # 0 或 1
    timeout: int | None = None


class RecordData(MessageNodeData):
    """语音消息数据"""

    file: str
    magic: int | None = None  # 0 或 1，变声
    url: str | None = None
    cache: int | None = None
    proxy: int | None = None
    timeout: int | None = None


class VideoData(MessageNodeData):
    """短视频消息数据"""

    file: str
    url: str | None = None
    cache: int | None = None
    proxy: int | None = None
    timeout: int | None = None


class AtData(MessageNodeData):
    """@某人消息数据"""

    qq: str  # QQ号 或 'all'
    name: str | None = None


class PokeData(MessageNodeData):
    """戳一戳消息数据"""

    type: str
    id: str
    name: str | None = None


class ShareData(MessageNodeData):
    """链接分享消息数据"""

    url: str
    title: str
    content: str | None = None
    image: str | None = None


class ContactData(MessageNodeData):
    """推荐好友/群消息数据"""

    type: str  # 'qq' 或 'group'
    id: str


class LocationData(MessageNodeData):
    """位置消息数据"""

    lat: str  # 纬度
    lon: str  # 经度
    title: str | None = None
    content: str | None = None


class MusicData(MessageNodeData):
    """音乐分享消息数据"""

    type: str  # 'qq', '163', 'xm' 或 'custom'
    id: str | None = None  # 非 custom 时使用
    url: str | None = None  # custom 时使用
    audio: str | None = None
    title: str | None = None
    content: str | None = None
    image: str | None = None


class ReplyData(MessageNodeData):
    """回复消息数据"""

    id: str | None = None  # msg_id 的短ID映射
    seq: int | None = None  # msg_seq，优先使用


class ForwardData(MessageNodeData):
    """合并转发消息数据"""

    id: str


class ForwardNodeData(MessageNodeData):
    """合并转发节点消息数据"""

    id: str | None = None  # 直接引用已有消息
    user_id: str | None = None  # 自定义节点
    nickname: str | None = None
    content: list | None = None  # MessageNode[]
    prompt: str | None = None
    summary: str | None = None
    source: str | None = None


class FileData(MessageNodeData):
    """文件消息数据"""

    file: str


class AnonymousData(MessageNodeData):
    """匿名发消息数据"""

    ignore: int | None = None  # 0 或 1


class RpsData(MessageNodeData):
    """猜拳魔法表情数据"""

    pass


class DiceData(MessageNodeData):
    """掷骰子魔法表情数据"""

    pass


class ShakeData(MessageNodeData):
    """窗口抖动数据"""

    pass


class XmlData(MessageNodeData):
    """XML消息数据"""

    data: str


class JsonData(MessageNodeData):
    """JSON消息数据"""

    data: str


# ==================== 消息段基类与子类 ====================


class MessageNode(BaseDataModel):
    """OneBot11 消息段基类

    使用 type 字段进行分发
    """

    discriminator_field: ClassVar[str] = "type"
    type: str

    @classmethod
    def build(cls, **kwargs: Any) -> Self:
        """根据具体消息段的 data 注解构造嵌套数据.
        (用于构造可通过API发送的消息链)"""
        data_field = cls.model_fields.get("data")
        if data_field is None:
            raise TypeError(f"{cls.__name__} 未声明 data 字段")

        annotations = (data_field.annotation, *get_args(data_field.annotation))
        data_types = [
            annotation
            for annotation in annotations
            if isinstance(annotation, type)
            and annotation is not MessageNodeData
            and issubclass(annotation, MessageNodeData)
        ]
        if len(data_types) != 1:
            raise TypeError(f"{cls.__name__}.data 未声明唯一的具体数据模型")

        data = data_types[0].model_validate(kwargs)
        return cls.model_validate({"data": data})


MessageNodeT = TypeVar("MessageNodeT", bound=MessageNode)


class TextNode(MessageNode):
    """纯文本消息段"""

    discriminator_value: ClassVar[str] = "text"
    type: str = "text"
    data: TextData

    @property
    def text(self) -> str:
        return self.data.text


class FaceNode(MessageNode):
    """QQ表情消息段"""

    discriminator_value: ClassVar[str] = "face"
    type: str = "face"
    data: FaceData

    @property
    def face_id(self) -> str:
        return self.data.id


class ImageNode(MessageNode):
    """图片消息段"""

    discriminator_value: ClassVar[str] = "image"
    type: str = "image"
    data: ImageData


class RecordNode(MessageNode):
    """语音消息段"""

    discriminator_value: ClassVar[str] = "record"
    type: str = "record"
    data: RecordData


class VideoNode(MessageNode):
    """短视频消息段"""

    discriminator_value: ClassVar[str] = "video"
    type: str = "video"
    data: VideoData


class AtNode(MessageNode):
    """@某人消息段"""

    discriminator_value: ClassVar[str] = "at"
    type: str = "at"
    data: AtData

    @property
    def qq(self) -> str:
        return self.data.qq

    @property
    def is_all(self) -> bool:
        return self.data.qq == "all"


class RpsNode(MessageNode):
    """猜拳魔法表情消息段"""

    discriminator_value: ClassVar[str] = "rps"
    type: str = "rps"
    data: RpsData | None = None


class DiceNode(MessageNode):
    """掷骰子魔法表情消息段"""

    discriminator_value: ClassVar[str] = "dice"
    type: str = "dice"
    data: DiceData | None = None


class ShakeNode(MessageNode):
    """窗口抖动消息段"""

    discriminator_value: ClassVar[str] = "shake"
    type: str = "shake"
    data: ShakeData | None = None


class PokeNode(MessageNode):
    """戳一戳消息段"""

    discriminator_value: ClassVar[str] = "poke"
    type: str = "poke"
    data: PokeData


class AnonymousNode(MessageNode):
    """匿名发消息消息段"""

    discriminator_value: ClassVar[str] = "anonymous"
    type: str = "anonymous"
    data: AnonymousData | None = None


class ShareNode(MessageNode):
    """链接分享消息段"""

    discriminator_value: ClassVar[str] = "share"
    type: str = "share"
    data: ShareData


class ContactNode(MessageNode):
    """推荐好友/群消息段"""

    discriminator_value: ClassVar[str] = "contact"
    type: str = "contact"
    data: ContactData


class LocationNode(MessageNode):
    """位置消息段"""

    discriminator_value: ClassVar[str] = "location"
    type: str = "location"
    data: LocationData


class MusicNode(MessageNode):
    """音乐分享消息段"""

    discriminator_value: ClassVar[str] = "music"
    type: str = "music"
    data: MusicData


class ReplyNode(MessageNode):
    """回复消息段"""

    discriminator_value: ClassVar[str] = "reply"
    type: str = "reply"
    data: ReplyData


class ForwardNode(MessageNode):
    """合并转发消息段"""

    discriminator_value: ClassVar[str] = "forward"
    type: str = "forward"
    data: ForwardData


class ForwardNodeNode(MessageNode):
    """合并转发节点消息段"""

    discriminator_value: ClassVar[str] = "node"
    type: str = "node"
    data: ForwardNodeData


class XmlNode(MessageNode):
    """XML消息段"""

    discriminator_value: ClassVar[str] = "xml"
    type: str = "xml"
    data: XmlData

    @property
    def xml_data(self) -> str:
        return self.data.data


class JsonNode(MessageNode):
    """JSON消息段"""

    discriminator_value: ClassVar[str] = "json"
    type: str = "json"
    data: JsonData

    @property
    def json_data(self) -> str:
        return self.data.data


class FileNode(MessageNode):
    """文件消息段"""

    discriminator_value: ClassVar[str] = "file"
    type: str = "file"
    data: FileData


# ==================== 消息列表领域模型 ====================


class NapcatMessage(AutoDispatchList[MessageNode]):
    """Napcat消息领域模型，包含一个消息段列表"""

    # root: list[MessageNode]

    @classmethod
    def element_type(cls):
        return MessageNode

    # 可迭代对象
    def __iter__(self):
        return iter(self.root)

    # 消息段构造方法
    def to_list_dict(self) -> list[dict]:
        """返回字典列表。"""
        return [
            type(node)
            .model_validate(node.model_dump(mode="python"))
            .model_dump(mode="json", exclude_none=True)
            for node in self
        ]

    # ====== 便携方法 ======

    @property
    def message_list(self) -> list[MessageNode]:
        """消息段列表"""
        return self.root

    def filter(self, node_type: type[MessageNodeT]) -> list[MessageNodeT]:
        """过滤出指定类型的消息段"""
        return [seg for seg in self.message_list if isinstance(seg, node_type)]

    @property
    def texts(self) -> list[str]:
        """提取所有文本消息段的文本内容"""
        return [seg.text for seg in self.filter(TextNode)]

    @property
    def ats(self) -> list[str]:
        """提取所有@消息段的QQ号"""
        return [seg.qq for seg in self.filter(AtNode)]

    @property
    def imgs(self) -> list[str]:
        """提取所有图片消息段的URL"""
        return [
            seg.data.url for seg in self.filter(ImageNode) if seg.data.url is not None
        ]

    @property
    def plain_text(self):
        """提取纯文本内容，连接所有文本消息段的文本"""
        return "".join(self.texts)


class NapcatMessageBuilder:
    """用于链式构造 NapCat 发送消息的建造器。"""

    def __init__(self) -> None:
        self._segments: list[MessageNode] = []

    # ====== 内部构造方法 ======

    def _add(self, segment: MessageNode) -> Self:
        """追加一个已构造的消息段。"""
        self._segments.append(segment)
        return self

    @staticmethod
    def _get_segments(
        other: "NapcatMessageBuilder | NapcatMessage | MessageNode",
    ) -> list[MessageNode] | None:
        if isinstance(other, NapcatMessageBuilder):
            return other._segments
        if isinstance(other, NapcatMessage):
            return other.message_list
        if isinstance(other, MessageNode):
            return [other]

    def _concatenate(
        self, other: "NapcatMessageBuilder | NapcatMessage | MessageNode"
    ) -> Self | NotImplementedType:
        if not isinstance(other, (NapcatMessageBuilder, NapcatMessage, MessageNode)):
            raise TypeError("合并非消息段内容: %r" % other)
        segments = self._get_segments(other)
        if segments is None:
            return NotImplemented
        builder = type(self)()
        builder._segments = [*self._segments, *segments]
        return builder

    # ====== 魔术方法 ======

    def __add__(
        self, other: "NapcatMessageBuilder | NapcatMessage | MessageNode"
    ) -> Self | NotImplementedType:
        """使用 ``+`` 拼接消息段，并返回新的建造器。"""
        return self._concatenate(other)

    def __and__(
        self, other: "NapcatMessageBuilder | NapcatMessage | MessageNode"
    ) -> Self | NotImplementedType:
        """使用 ``&`` 拼接消息段，并返回新的建造器。"""
        return self._concatenate(other)

    # ====== 对外追加构造方法 ======

    def text(self, text: str) -> Self:
        """追加纯文本消息段。"""
        return self._add(TextNode.build(text=text))

    def at(self, qq: str | int, name: str | None = None) -> Self:
        """追加 @ 某人的消息段。"""
        return self._add(AtNode.build(qq=str(qq), name=name))

    def at_all(self) -> Self:
        """追加 @全体成员 消息段。"""
        return self.at("all")

    def image(
        self,
        file: str,
        *,
        image_type: str | None = None,
        url: str | None = None,
        cache: int | None = None,
        proxy: int | None = None,
        timeout: int | None = None,
    ) -> Self:
        """追加图片消息段。"""
        return self._add(
            ImageNode.build(
                file=file,
                type=image_type,
                url=url,
                cache=cache,
                proxy=proxy,
                timeout=timeout,
            )
        )

    def reply(
        self, message_id: str | int | None = None, seq: int | None = None
    ) -> Self:
        """追加回复消息段。"""
        return self._add(
            ReplyNode.build(id=None if message_id is None else str(message_id), seq=seq)
        )

    def face(self, face_id: str) -> Self:
        """追加 QQ 表情消息段。"""
        return self._add(FaceNode.build(id=face_id))

    def record(
        self,
        file: str,
        *,
        magic: int | None = None,
        url: str | None = None,
        cache: int | None = None,
        proxy: int | None = None,
        timeout: int | None = None,
    ) -> Self:
        """追加语音消息段。"""
        return self._add(
            RecordNode.build(
                file=file,
                magic=magic,
                url=url,
                cache=cache,
                proxy=proxy,
                timeout=timeout,
            )
        )

    def video(
        self,
        file: str,
        *,
        url: str | None = None,
        cache: int | None = None,
        proxy: int | None = None,
        timeout: int | None = None,
    ) -> Self:
        """追加短视频消息段。"""
        return self._add(
            VideoNode.build(
                file=file, url=url, cache=cache, proxy=proxy, timeout=timeout
            )
        )

    def poke(self, poke_type: str, poke_id: str | int, name: str | None = None) -> Self:
        """追加戳一戳消息段。"""
        return self._add(PokeNode.build(type=poke_type, id=str(poke_id), name=name))

    def share(
        self,
        url: str,
        title: str,
        *,
        content: str | None = None,
        image: str | None = None,
    ) -> Self:
        """追加链接分享消息段。"""
        return self._add(
            ShareNode.build(url=url, title=title, content=content, image=image)
        )

    def contact(self, contact_type: str, contact_id: str | int) -> Self:
        """追加推荐好友或群消息段。"""
        return self._add(ContactNode.build(type=contact_type, id=str(contact_id)))

    def location(
        self,
        lat: str | float,
        lon: str | float,
        *,
        title: str | None = None,
        content: str | None = None,
    ) -> Self:
        """追加位置消息段。"""
        return self._add(
            LocationNode.build(lat=str(lat), lon=str(lon), title=title, content=content)
        )

    def music(
        self,
        music_type: str,
        *,
        music_id: str | None = None,
        url: str | None = None,
        audio: str | None = None,
        title: str | None = None,
        content: str | None = None,
        image: str | None = None,
    ) -> Self:
        """追加音乐分享消息段。"""
        return self._add(
            MusicNode.build(
                type=music_type,
                id=music_id,
                url=url,
                audio=audio,
                title=title,
                content=content,
                image=image,
            )
        )

    def file(self, file: str) -> Self:
        """追加文件消息段。"""
        return self._add(FileNode.build(file=file))

    def anonymous(self, ignore: int | None = None) -> Self:
        """追加匿名发消息段。"""
        return self._add(AnonymousNode.build(ignore=ignore))

    def rps(self) -> Self:
        """追加猜拳魔法表情消息段。"""
        return self._add(RpsNode.build())

    def dice(self) -> Self:
        """追加掷骰子魔法表情消息段。"""
        return self._add(DiceNode.build())

    def shake(self) -> Self:
        """追加窗口抖动消息段。"""
        return self._add(ShakeNode.build())

    def xml(self, data: str) -> Self:
        """追加 XML 消息段。"""
        return self._add(XmlNode.build(data=data))

    def json(self, data: str) -> Self:
        """追加 JSON 消息段。"""
        return self._add(JsonNode.build(data=data))

    def build(self) -> NapcatMessage:
        """构造独立的消息领域模型。"""
        return NapcatMessage(list(self._segments))
