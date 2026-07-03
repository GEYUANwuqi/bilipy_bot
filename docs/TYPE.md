# 如何适配一个 Type 类

本章将介绍如何基于 `BaseType` 基类适配事件标签枚举类。

------

## 基类说明

```python
class BaseType(str, Enum):
    """标签枚举基类，提供通用的匹配方法."""

    @property
    def scope(self) -> str:
        """返回标签的作用域."""
        return self.value.split(".", 1)[0]

    @property
    def state(self) -> str:
        """返回标签的状态."""
        return self.value.split(".", 1)[1]

    def matches(self, rule: "BaseType") -> bool:
        """判断状态是否匹配.

        Args:
            rule: 要匹配的标签

        Returns:
            bool: 匹配结果
        """
        if type(self) is type(rule):  # Type匹配
            if self.scope == rule.scope:  # 作用域匹配
                # 精确匹配、通配、或层级父匹配子（如 "message" 匹配 "message.group"）
                if (
                    self.state == rule.state
                    or rule.state == "all"
                    or self.state.startswith(rule.state + ".")
                ):
                    return True
                return False
            return False
        return False

BaseTypeT = TypeVar("BaseTypeT", bound=BaseType)
```

`BaseType` 提供了以下方法：

- `matches(rule)`：判断当前标签是否匹配给定规则
- `matching_statuses(rule)`：（类方法）返回当前枚举类中所有匹配给定规则的成员

- 标签值格式：`scope.state`（如 `"dynamic.new"`）
- `scope`：作用域，表示事件类别
- `state`：状态，表示具体事件类型
- 通配符：`"all"` 匹配同一作用域下的所有状态
- 层级匹配：父状态自动匹配子状态（如 `"message"` 匹配 `"message.group"`）

------

## 适配步骤

### 1. 定义枚举类

继承 `BaseType` 并定义事件标签：

```python
from bilipy_bot.core.types import BaseType

class MyType(BaseType):
    """我的事件类型枚举."""
    ALL = "my.all"           # 通配符，表示所有状态
    MESSAGE = "my.message"   # 消息事件
    NOTICE = "my.notice"     # 通知事件
    REQUEST = "my.request"   # 请求事件
```

### 2. 使用标签

在事件订阅和发布时使用标签：

```python
from bilipy_bot.core.event import Event

# 发布事件
event = Event(data=data, status=MyType.MESSAGE)
await self.ctx.bus.publish(self.uuid, event)

# 订阅事件（订阅所有消息事件）
@app.subscribe(source_id, MyType.MESSAGE)
async def handle_message(event: Event):
    pass

# 订阅事件（订阅所有事件）
@app.subscribe(source_id, MyType.ALL)
async def handle_all(event: Event):
    pass
```

------

## 标签匹配规则

### 基本匹配

```python
# 相同类型、相同作用域、相同状态
MyType.MESSAGE.matches(MyType.MESSAGE)  # True

# 相同类型、相同作用域、不同状态
MyType.MESSAGE.matches(MyType.NOTICE)  # False

# 不同类型
DynamicType.NEW.matches(MyType.MESSAGE)  # False
```

### 批量匹配（订阅规则编译）

```python
# matching_statuses 返回枚举类中所有匹配给定规则的成员（排除 "all" 通配符）

# BaseType 规则
MyType.matching_statuses(MyType.MESSAGE)         # → [MyType.MESSAGE]
MyType.matching_statuses(MyType.ALL)             # → [MyType.MESSAGE, MyType.NOTICE, ...]（所有具体状态）

# str 正则需要展开
MyType.matching_statuses(r"my_source\.message")  # → [MyType.MESSAGE]

# re.Pattern 展开
import re
pat = re.compile(r"my_source\.(message|notice)")
MyType.matching_statuses(pat)                    # → [MyType.MESSAGE, MyType.NOTICE]
```

该方法用于框架内部的订阅规则编译：将用户的订阅规则在注册期一次性展开为具体状态值，
使运行时事件发布退化为 O(1) 查表派发。

### 通配符匹配

```python
# 通配符匹配同一作用域下的所有状态
MyType.MESSAGE.matches(MyType.ALL)  # True
MyType.NOTICE.matches(MyType.ALL)  # True
MyType.REQUEST.matches(MyType.ALL)  # True

# 通配符不能匹配具体状态
MyType.ALL.matches(MyType.MESSAGE)  # False
```

### 层级匹配

当状态值使用点号形成层级结构时（如 `"message.group"`），父状态自动匹配子状态：

```python
# 父状态匹配子状态
MyType.GROUP_MESSAGE.matches(MyType.MESSAGE)  # True
MyType.PRIVATE_MESSAGE.matches(MyType.MESSAGE)  # True

# 子状态不反向匹配父状态（单向）
MyType.MESSAGE.matches(MyType.GROUP_MESSAGE)  # False

# ALL 仍通配所有层级
MyType.GROUP_MESSAGE.matches(MyType.ALL)  # True
```

------

## 完整示例

以下是一个完整的 Type 适配示例，参考 [napcat_type](../bilipy_bot/sources/napcat/types/napcat_type.py)：

```python
from typing import Any
from bilipy_bot.core.types import BaseType


class NapcatType(BaseType):
    """NapCat 事件类型枚举——支持层级匹配."""

    # 通配
    ALL = "napcat.all"
    UNKNOWN = "napcat.unknown"

    # 元事件
    META = "napcat.meta"
    LIFECYCLE_META = "napcat.meta.lifecycle"
    HEARTBEAT_META = "napcat.meta.heartbeat"

    # 消息事件
    MESSAGE = "napcat.message"
    GROUP_MESSAGE = "napcat.message.group"
    PRIVATE_MESSAGE = "napcat.message.private"

    # 自身消息
    SENT = "napcat.sent"
    GROUP_SENT = "napcat.sent.group"
    PRIVATE_SENT = "napcat.sent.private"

    # 请求事件
    REQUEST = "napcat.request"
    FRIEND_REQUEST = "napcat.request.friend"
    GROUP_REQUEST = "napcat.request.group"

    # 通知事件
    NOTICE = "napcat.notice"
    GROUP_UPLOAD_NOTICE = "napcat.notice.group_upload"
    POKE_NOTIFY = "napcat.notice.poke"
    # ...

    @classmethod
    def get_specific_type(cls, message: dict[str, Any]) -> "NapcatType":
        """根据完整消息字典返回最具体的 NapcatType."""
        post_type = message.get("post_type", "")
        if post_type == "message":
            if message.get("message_type") == "group":
                return NapcatType.GROUP_MESSAGE
            elif message.get("message_type") == "private":
                return NapcatType.PRIVATE_MESSAGE
            return NapcatType.MESSAGE
        if post_type == "notice":
            # 按 notice_type 进一步分发...
            ...
        # ... 其他 post_type
        return NapcatType.UNKNOWN
```

------

## 多事件源场景

当有多个事件源时，每个事件源应该定义自己的 Type 类：

```python
from bilipy_bot.core.types import BaseType


# ========== B站事件类型 ==========

class DynamicType(BaseType):
    """动态状态枚举."""
    ALL = "dynamic.all"
    NEW = "dynamic.new"
    DELETED = "dynamic.deleted"
    NULL = "dynamic.null"


class LiveType(BaseType):
    """直播状态枚举."""
    ALL = "live.all"
    ONLINE = "live.online"
    OFFLINE = "live.offline"
    OPEN = "live.open"
    CLOSE = "live.close"


# ========== QQ事件类型 ==========

class NapcatType(BaseType):
    """napcat状态枚举（支持层级匹配）."""
    ALL = "napcat.all"
    MESSAGE = "napcat.message"
    GROUP_MESSAGE = "napcat.message.group"
    PRIVATE_MESSAGE = "napcat.message.private"
    NOTICE = "napcat.notice"
```

这样可以避免不同事件源的标签冲突，同时也更清晰地组织代码。

------

## 参考实现

- [napcat_type](../bilipy_bot/sources/napcat/type/napcat_type.py)：NapCat 事件类型枚举
- [bilibili_type](../bilipy_bot/sources/bilibili/type/bili_type.py)：B站事件类型枚举
