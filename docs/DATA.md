# 如何适配一个 Data 数据类

本章将介绍如何基于 `BaseDataMixin` 和 `BaseDataModel` 适配数据类。

------

## 基类说明

### BaseDataMixin

```python
class BaseDataMixin:
    """
    框架内约束的数据类混入类, 用于标记框架内数据
    """
    _repr_exclude = {"raw_data"}  # 排除在repr中的属性集合

    def __repr__(self):
        core_properties_str: str = self._get_core_properties_str()
        return f"{self.__class__.__name__}({core_properties_str})"

    def __str__(self):
        return self.__repr__()

    def _get_core_properties_str(self) -> str:
        excludes = set(getattr(self, "_repr_exclude", ()))
        props = {
            k: v
            for k, v in vars(self).items()
            if not k.startswith("_") and k not in excludes
        }
        parts = [f"{k}={repr(v)}" for k, v in props.items()]
        return ", ".join(parts)

BaseDataT = TypeVar("BaseDataT", bound=BaseDataMixin)
```

`BaseDataMixin` 提供了一个统一的 `__repr__` 和 `__str__` 方法实现，方便调试时输出核心属性信息。

- 子类可以通过定义 `_repr_exclude` 属性来指定哪些属性不应该包含在输出中
- 只要这个类混入了 `BaseDataMixin` 就会被框架认为是框架内传输的数据对象

------

### BaseDataModel

```python
class BaseDataModel(BaseModel, BaseDataMixin, metaclass=MetaDataModel):
    """
    基于BaseDataMixin实现的领域模型基类
    1. 使用pydantic进行数据校验
    2. 支持单层和多层继承的 discriminator 注册机制
    3. 根类定义 discriminator_field，子类定义 discriminator_value，自动注册到 registry
    """
    model_config = ConfigDict(
        strict = False,  # 强制转换数据
        frozen = True,  # 实例不可变，自动生成 __hash__
        extra = 'ignore',  # 额外字段将被忽略
    )

    _registry: ClassVar[dict] = {}

    @classmethod
    def from_raw(cls, raw: dict) -> Self:
        """从原始数据构造实例，可实现复杂构造逻辑"""
        pass

    @classmethod
    def from_dict(cls, raw: dict) -> Self:
        """从dict自动构造实例，支持多层分发"""
        pass

    @classmethod
    def from_type(cls, data: dict, type_value: str, raw: bool = True) -> Self:
        """根据指定的type_value从dict构造实例"""
        pass
```

`BaseDataModel` 提供了基于 pydantic 的数据校验和自动分发机制。

- `discriminator_field`：分发依据的"键"，必须在根/基类定义
- `discriminator_value`：分发依据的"值"，子类定义
- `from_dict()`：自动根据 `discriminator_field` 分发到对应的子类
- `from_raw()`：可选的自定义构造逻辑

------

## 适配方式

### 方式一：使用 dataclass（简单场景）

对于简单的数据结构，可以使用 `dataclass` + `BaseDataMixin`：

```python
from dataclasses import dataclass
from bilipy_bot.app.data import BaseDataMixin

@dataclass(frozen=True)
class UserData(BaseDataMixin):
    """用户数据"""
    user_id: int
    nickname: str
    avatar: str

    @classmethod
    def from_dict(cls, data: dict) -> "UserData":
        """从字典构造实例"""
        return cls(
            user_id=data["user_id"],
            nickname=data["nickname"],
            avatar=data["avatar"],
        )
```

------

### 方式二：使用 BaseDataModel（复杂场景）

对于需要自动分发的复杂数据结构，使用 `BaseDataModel`：

#### 单层分发

```python
from typing import ClassVar
from bilipy_bot.app.data import BaseDataModel

class Event(BaseDataModel):
    """事件基类"""
    discriminator_field: ClassVar[str] = "event_type"
    event_type: str
    data: dict

class MessageEvent(Event):
    """消息事件"""
    discriminator_value: ClassVar[str] = "message"
    event_type: str = "message"
    message_id: int
    content: str

class NoticeEvent(Event):
    """通知事件"""
    discriminator_value: ClassVar[str] = "notice"
    event_type: str = "notice"
    notice_type: str
```

使用方式：

```python
# 自动分发到对应的子类
raw_data = {"event_type": "message", "message_id": 123, "content": "hello"}
event = Event.from_dict(raw_data)  # 返回 MessageEvent 实例
```

#### 多层分发

```python
from typing import ClassVar
from bilipy_bot.app.data import BaseDataModel

class Event(BaseDataModel):
    """事件基类 - 第一层分发"""
    discriminator_field: ClassVar[str] = "post_type"
    post_type: str

class MessageEvent(Event):
    """消息事件 - 第二层分发"""
    discriminator_value: ClassVar[str] = "message"
    discriminator_field: ClassVar[str] = "message_type"
    post_type: str = "message"
    message_type: str

class PrivateMessageEvent(MessageEvent):
    """私聊消息"""
    discriminator_value: ClassVar[str] = "private"
    message_type: str = "private"
    user_id: int

class GroupMessageEvent(MessageEvent):
    """群消息"""
    discriminator_value: ClassVar[str] = "group"
    message_type: str = "group"
    group_id: int
```

使用方式：

```python
# 多层自动分发
raw_data = {
    "post_type": "message",
    "message_type": "group",
    "group_id": 123456,
    "user_id": 789,
}
event = Event.from_dict(raw_data)  # 返回 GroupMessageEvent 实例
```

------

## 完整示例

以下是一个完整的数据类适配示例，参考 [napcat 事件数据](../bilipy_bot/sources/napcat/data/event_data.py)：

```python
"""
OneBot11 事件数据模型
"""
from typing import ClassVar, Optional
from bilipy_bot.app.data import BaseDataModel


# ==================== 嵌套数据类 ====================

class Sender(BaseDataModel):
    """发送者信息"""
    user_id: int
    nickname: str
    card: Optional[str] = None


# ==================== 事件基类 ====================

class OneBotEvent(BaseDataModel):
    """OneBot11 事件基类

    使用 post_type 字段进行一级分发
    """
    discriminator_field: ClassVar[str] = "post_type"
    time: int
    self_id: int
    post_type: str


# ==================== 消息事件 ====================

class MessageEvent(OneBotEvent):
    """消息事件基类

    使用 message_type 字段进行二级分发
    """
    discriminator_value: ClassVar[str] = "message"
    discriminator_field: ClassVar[str] = "message_type"
    post_type: str = "message"
    message_type: str
    sub_type: str
    message_id: int
    user_id: int
    message: str
    raw_message: str
    font: int


class PrivateMessageEvent(MessageEvent):
    """私聊消息事件"""
    discriminator_value: ClassVar[str] = "private"
    message_type: str = "private"
    sub_type: str = "friend"
    target_id: Optional[int] = None
    sender: Sender


class GroupMessageEvent(MessageEvent):
    """群消息事件"""
    discriminator_value: ClassVar[str] = "group"
    message_type: str = "group"
    sub_type: str = "normal"
    group_id: int
    sender: Sender


# ==================== 通知事件 ====================

class NoticeEvent(OneBotEvent):
    """通知事件基类

    使用 notice_type 字段进行二级分发
    """
    discriminator_value: ClassVar[str] = "notice"
    discriminator_field: ClassVar[str] = "notice_type"
    post_type: str = "notice"
    notice_type: str


class GroupUploadNoticeEvent(NoticeEvent):
    """群文件上传事件"""
    discriminator_value: ClassVar[str] = "group_upload"
    notice_type: str = "group_upload"
    group_id: int
    user_id: int
    file_id: str
    file_name: str
```

------

## DTO 模式

对于复杂的数据转换，建议使用 DTO（Data Transfer Object）模式：

```python
from dataclasses import dataclass
from typing import Optional
from bilipy_bot.app.data import BaseDataModel, BaseDataMixin


# ========== DTO 层（处理原始数据） ==========

class UserDTO(BaseDataModel):
    """用户 DTO"""
    uid: int
    name: str
    face: str


# ========== Data 层（业务数据对象） ==========

@dataclass(frozen=True)
class UserData(BaseDataMixin):
    """用户数据"""
    user_id: int
    nickname: str
    avatar_url: str

    @classmethod
    def from_dto(cls, dto: UserDTO) -> "UserData":
        """从 DTO 构造实例"""
        return cls(
            user_id=dto.uid,
            nickname=dto.name,
            avatar_url=dto.face,
        )
```

------

## 参考实现

- [napcat 事件数据](../bilipy_bot/sources/napcat/data/event_data.py)：NapCat 事件数据模型
- [napcat 消息段数据](../bilipy_bot/sources/napcat/data/segment_data.py)：NapCat 消息段数据模型
- [bilibili 动态数据](../bilipy_bot/sources/bilibili/data/dynamic_data.py)：B站动态数据模型
- [bilibili 直播间数据](../bilipy_bot/sources/bilibili/data/live_room_data.py)：B站直播间数据模型
