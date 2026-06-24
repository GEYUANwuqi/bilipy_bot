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
            bool: 在作用域相同且具体状态相同或rule为通配符时返回True，否则返回False
        """
        if type(self) is type(rule):  # Type匹配
            if self.scope == rule.scope:  # 作用域匹配
                if self.state == rule.state:  # 具体状态匹配
                    return True
                elif rule.state == "all":  # 通配符
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False

BaseTypeT = TypeVar("BaseTypeT", bound=BaseType)
```

`BaseType` 提供了一个公共的方法 `matches()` 用于判断两个标签是否匹配。

- 标签值格式：`scope.state`（如 `"dynamic.new"`）
- `scope`：作用域，表示事件类别
- `state`：状态，表示具体事件类型
- 通配符：`"all"` 匹配同一作用域下的所有状态

------

## 适配步骤

### 1. 定义枚举类

继承 `BaseType` 并定义事件标签：

```python
from bilipy_bot.app.type import BaseType

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
from bilipy_bot.app.event import Event

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

### 通配符匹配

```python
# 通配符匹配同一作用域下的所有状态
MyType.MESSAGE.matches(MyType.ALL)  # True
MyType.NOTICE.matches(MyType.ALL)  # True
MyType.REQUEST.matches(MyType.ALL)  # True

# 通配符不能匹配具体状态
MyType.ALL.matches(MyType.MESSAGE)  # False
```

------

## 完整示例

以下是一个完整的 Type 适配示例，参考 [napcat_type](../bilipy_bot/sources/napcat/type/napcat_type.py)：

```python
from bilipy_bot.app.type import BaseType


class NapcatType(BaseType):
    """napcat状态枚举."""
    ALL = "napcat.all"         # 通配符
    META = "napcat.meta"       # 元信息
    MESSAGE = "napcat.message" # 群/私聊消息
    REQUEST = "napcat.request" # 请求消息
    NOTICE = "napcat.notice"   # 通知消息
    SENT = "napcat.sent"       # 自身消息
    UNKNOWN = "napcat.unknown" # 未知消息

    @classmethod
    def get_type(cls, post_type: str) -> "NapcatType":
        """根据 post_type 返回对应的枚举实例.

        Args:
            post_type: 事件类型字符串

        Returns:
            NapcatType 枚举实例
        """
        if post_type == "meta_event":
            return NapcatType.META
        elif post_type == "message":
            return NapcatType.MESSAGE
        elif post_type == "request":
            return NapcatType.REQUEST
        elif post_type == "notice":
            return NapcatType.NOTICE
        elif post_type == "message_sent":
            return NapcatType.SENT
        else:
            return NapcatType.UNKNOWN
```

------

## 多事件源场景

当有多个事件源时，每个事件源应该定义自己的 Type 类：

```python
from bilipy_bot.app.type import BaseType


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
    """napcat状态枚举."""
    ALL = "napcat.all"
    MESSAGE = "napcat.message"
    NOTICE = "napcat.notice"
```

这样可以避免不同事件源的标签冲突，同时也更清晰地组织代码。

------

## 参考实现

- [napcat_type](../bilipy_bot/sources/napcat/type/napcat_type.py)：NapCat 事件类型枚举
- [bilibili_type](../bilipy_bot/sources/bilibili/type/bili_type.py)：B站事件类型枚举
