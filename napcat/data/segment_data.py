"""
NapCat OneBot11 消息段数据模型

基于 OneBot11 协议定义的消息段类型，使用 BaseDataModel 实现自动分发构造
"""
from typing import ClassVar, Optional, TypeVar

from base_cls import BaseDataModel, AutoDispatchList


# ==================== 嵌套数据类 ====================

class TextData(BaseDataModel):
    """纯文本消息数据"""
    text: str


class FaceData(BaseDataModel):
    """QQ表情消息数据"""
    id: str


class ImageData(BaseDataModel):
    """图片消息数据"""
    file: str
    type: Optional[str] = None  # 'flash' 表示闪照
    url: Optional[str] = None
    cache: Optional[int] = None  # 0 或 1
    proxy: Optional[int] = None  # 0 或 1
    timeout: Optional[int] = None


class RecordData(BaseDataModel):
    """语音消息数据"""
    file: str
    magic: Optional[int] = None  # 0 或 1，变声
    url: Optional[str] = None
    cache: Optional[int] = None
    proxy: Optional[int] = None
    timeout: Optional[int] = None


class VideoData(BaseDataModel):
    """短视频消息数据"""
    file: str
    url: Optional[str] = None
    cache: Optional[int] = None
    proxy: Optional[int] = None
    timeout: Optional[int] = None


class AtData(BaseDataModel):
    """@某人消息数据"""
    qq: str  # QQ号 或 'all'
    name: Optional[str] = None


class PokeData(BaseDataModel):
    """戳一戳消息数据"""
    type: str
    id: str
    name: Optional[str] = None


class ShareData(BaseDataModel):
    """链接分享消息数据"""
    url: str
    title: str
    content: Optional[str] = None
    image: Optional[str] = None


class ContactData(BaseDataModel):
    """推荐好友/群消息数据"""
    type: str  # 'qq' 或 'group'
    id: str


class LocationData(BaseDataModel):
    """位置消息数据"""
    lat: str  # 纬度
    lon: str  # 经度
    title: Optional[str] = None
    content: Optional[str] = None


class MusicData(BaseDataModel):
    """音乐分享消息数据"""
    type: str  # 'qq', '163', 'xm' 或 'custom'
    id: Optional[str] = None  # 非 custom 时使用
    url: Optional[str] = None  # custom 时使用
    audio: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    image: Optional[str] = None


class ReplyData(BaseDataModel):
    """回复消息数据"""
    id: Optional[str] = None  # msg_id 的短ID映射
    seq: Optional[int] = None  # msg_seq，优先使用


class ForwardData(BaseDataModel):
    """合并转发消息数据"""
    id: str


class NodeData(BaseDataModel):
    """合并转发节点消息数据"""
    id: Optional[str] = None  # 直接引用已有消息
    user_id: Optional[str] = None  # 自定义节点
    nickname: Optional[str] = None
    content: Optional[list] = None  # MessageNode[]
    prompt: Optional[str] = None
    summary: Optional[str] = None
    source: Optional[str] = None


class FileData(BaseDataModel):
    """文件消息数据"""
    file: str


class AnonymousData(BaseDataModel):
    """匿名发消息数据"""
    ignore: Optional[int] = None  # 0 或 1


class RpsData(BaseDataModel):
    """猜拳魔法表情数据"""
    pass


class DiceData(BaseDataModel):
    """掷骰子魔法表情数据"""
    pass


class ShakeData(BaseDataModel):
    """窗口抖动数据"""
    pass


class XmlData(BaseDataModel):
    """XML消息数据"""
    data: str


class JsonData(BaseDataModel):
    """JSON消息数据"""
    data: str


# ==================== 消息段基类与子类 ====================

class MessageNode(BaseDataModel):
    """OneBot11 消息段基类

    使用 type 字段进行分发
    """
    discriminator_field: ClassVar[str] = "type"
    type: str


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
    data: Optional[RpsData] = None


class DiceNode(MessageNode):
    """掷骰子魔法表情消息段"""
    discriminator_value: ClassVar[str] = "dice"
    type: str = "dice"
    data: Optional[DiceData] = None


class ShakeNode(MessageNode):
    """窗口抖动消息段"""
    discriminator_value: ClassVar[str] = "shake"
    type: str = "shake"
    data: Optional[ShakeData] = None


class PokeNode(MessageNode):
    """戳一戳消息段"""
    discriminator_value: ClassVar[str] = "poke"
    type: str = "poke"
    data: PokeData


class AnonymousNode(MessageNode):
    """匿名发消息消息段"""
    discriminator_value: ClassVar[str] = "anonymous"
    type: str = "anonymous"
    data: Optional[AnonymousData] = None


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


class NodeNode(MessageNode):
    """合并转发节点消息段"""
    discriminator_value: ClassVar[str] = "node"
    type: str = "node"
    data: NodeData


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

    # dict()
    def __iter__(self):
        return iter(self.root)

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
        return [seg.data.url for seg in self.filter(ImageNode) if seg.data.url is not None]

    @property
    def plain_text(self):
        """提取纯文本内容，连接所有文本消息段的文本"""
        return "".join(self.texts)
