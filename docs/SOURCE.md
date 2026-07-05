# 如何适配一个完整的 Source 事件源

本章将介绍如何基于 `BaseSource` 基类适配一个完整的事件源。

------

## 基类说明

```python
class BaseSource(ABC):
    """事件源基类.

    Attributes:
        uuid: 唯一标识符，由 SourceManager 内部管理
        running: 运行状态
        supported_types: ``BaseType`` 枚举类，声明该事件源所能发出的所有事件类型
    """

    supported_types: ClassVar[type[BaseType] | None] = None

    @abstractmethod
    def __init__(self, **kwargs):
        """初始化事件源."""
        self.uuid: UUID = uuid4()
        self.running: bool = False
        self._ctx: "AppContext | None" = None

    @abstractmethod
    async def start(self) -> None:
        """启动事件源."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止事件源."""
        pass

    def bind(self, ctx: "AppContext") -> None:
        """绑定应用上下文."""
        self._ctx = ctx

    @property
    def ctx(self) -> "AppContext":
        """获取应用上下文."""
        if self._ctx is None:
            raise RuntimeError("Source 尚未绑定上下文，请先调用 bind()")
        return self._ctx

    @property
    def is_running(self) -> bool:
        """检查是否正在运行."""
        return self.running

BaseSourceT = TypeVar("BaseSourceT", bound=BaseSource)
```

`BaseSource` 定义了事件源的基本接口：

- `__init__`：初始化事件源，**必须先调用** `super().__init__()` 来初始化基本属性
- `start()`：启动事件源，由 SourceManager 调用
- `stop()`：停止事件源，由 SourceManager 调用
- `bind()`：绑定应用上下文，由 SourceManager 在启动时调用
- `ctx`：获取应用上下文（在 bind 之后才能使用）

> 注：`bind` 方法在 `SourceManager` 启动时调用，当事件源初始化时，它是不持有上下文的

### 声明 supported_types（必须）

每个事件源**必须**声明 `supported_types` 类属性，指定该事件源所能发出的所有事件类型：

```python
from bilipy_bot.core.types import BaseType

class MySourceType(BaseType):
    ALL = "my_source.all"
    MESSAGE = "my_source.message"
    NOTICE = "my_source.notice"


class MySource(BaseSource):
    supported_types = MySourceType  # <-- 声明事件类型枚举
    ...
```

`supported_types` 的作用：

- **订阅规则编译**：框架在注册订阅时，根据此声明将订阅规则（`BaseType`、`str` 正则或 `re.Pattern`）展开为具体状态值，建立 `uuid → status → callbacks` 的派发表
- **运行时优化**：事件发布时直接 O(1) 查表触发回调，无需遍历和匹配
- **未声明的后果**：未设置 `supported_types` 的 Source 在订阅时会抛出 `TypeError`

------

## 目录结构

一个完整的事件源通常包含以下目录结构：

```
my_source/
├── __init__.py          # 导出公共接口
├── api/
│   ├── __init__.py
│   └── my_api.py        # API 实现
├── data/
│   ├── __init__.py
│   ├── event_data.py    # 事件数据模型
│   └── dto/             # 数据传输对象（可选）
├── source/
│   ├── __init__.py
│   └── my_source.py     # 事件源实现
└── type/
    ├── __init__.py
    └── my_type.py       # 事件类型枚举
```

------

## 适配步骤

### 1. 定义事件类型

首先定义事件类型枚举：

```python
# my_source/types/my_type.py
from bilipy_bot.core.types import BaseType

class MySourceType(BaseType):
    """我的事件源类型枚举."""
    ALL = "my_source.all"         # 通配符
    MESSAGE = "my_source.message" # 消息事件
    NOTICE = "my_source.notice"   # 通知事件
```

### 2. 定义数据模型

定义事件数据模型：

```python
# my_source/data/event_data.py
from typing import ClassVar
from bilipy_bot.core.data import BaseDataModel

class MyEvent(BaseDataModel):
    """事件基类"""
    discriminator_field: ClassVar[str] = "event_type"
    event_type: str
    timestamp: int

class MessageEvent(MyEvent):
    """消息事件"""
    discriminator_value: ClassVar[str] = "message"
    event_type: str = "message"
    message_id: int
    content: str
    sender_id: int

class NoticeEvent(MyEvent):
    """通知事件"""
    discriminator_value: ClassVar[str] = "notice"
    event_type: str = "notice"
    notice_type: str
```

### 3. 实现 API

实现 API 模块：

```python
# my_source/api/my_api.py
from bilipy_bot.core.api import BaseApi
from bilipy_bot.core.context import ApiRegistry
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from bilipy_bot.core.context import ApiRegistry

class MyApi(BaseApi):
    """我的 API 实现"""

    @classmethod
    def create(cls, ctx: "ApiRegistry", config_key: str = "my_source") -> "MyApi":
        """从上下文创建实例"""
        config = ctx.config.get_config(config_key)
        return cls(config)

    def __init__(self, config):
        self.config = config
        # 初始化客户端...

    async def start(self):
        """启动客户端"""
        pass

    async def stop(self):
        """停止客户端"""
        pass

    async def get_messages(self) -> list[dict]:
        """获取消息"""
        pass
```

### 4. 实现事件源

实现事件源：

```python
# my_source/source/my_source.py
from typing import Any
from logging import getLogger

from bilipy_bot.core.source import BaseSource
from bilipy_bot.core.event import Event
from bilipy_bot.sources.my_source.api import MyApi
from bilipy_bot.sources.my_source.data import MyEvent
from bilipy_bot.sources.my_source.types import MySourceType

_log = getLogger("MySource")


class MySource(BaseSource):
    """我的事件源.

    通过轮询或 WebSocket 接收事件并发布到 EventBus。
    """

    supported_types = MySourceType

    def __init__(self, config_key: str = "my_source"):
        """初始化事件源.

        Args:
            config_key: 配置键
        """
        super().__init__()  # 必须调用
        self.config_key = config_key

    async def start(self) -> None:
        """启动事件源."""
        # 设置消息处理函数
        self.api.set_handler(self._process_messages)
        # 启动 API 客户端
        await self.api.start()
        _log.info("事件源已启动")

    async def stop(self) -> None:
        """停止事件源."""
        await self.api.stop()
        _log.info("事件源已停止")

    @property
    def api(self) -> MyApi:
        """获取 API 实例."""
        return self.ctx.api_ctx.get(MyApi, self.config_key)

    async def _process_messages(self, message: dict[str, Any]) -> None:
        """处理接收到的消息.

        Args:
            message: 原始消息字典
        """
        try:
            # 使用 BaseDataModel 的自动分发构造
            event_data = MyEvent.from_dict(message)

            # 确定事件类型
            event_type = self._get_event_type(message)

            # 创建事件并发布
            event = Event(data=event_data, status=event_type)
            await self.ctx.bus.publish(self.uuid, event)

        except Exception as e:
            _log.error("处理消息失败: %s, 原始消息: %s", e, message)

    def _get_event_type(self, message: dict) -> MySourceType:
        """根据消息内容确定事件类型.

        Args:
            message: 原始消息字典

        Returns:
            事件类型枚举值
        """
        event_type = message.get("event_type", "")
        if event_type == "message":
            return MySourceType.MESSAGE
        elif event_type == "notice":
            return MySourceType.NOTICE
        else:
            return MySourceType.ALL
```

### 5. 定义模块导出

```python
# my_source/__init__.py
from .source.my_source import MySource
from .api.my_api import MyApi
from .type.my_type import MySourceType

__all__ = [
    "MySource",
    "MyApi",
    "MySourceType",
]
```

------

## 完整示例

以下是一个完整的事件源适配示例，参考 [napcat_source](../bilipy_bot/sources/napcat/source/napcat_source.py)：

```python
"""
Napcat 事件源
"""
from typing import Any, Optional
from logging import getLogger

from bilipy_bot.core.source import BaseSource
from bilipy_bot.core.event import Event
from bilipy_bot.sources.napcat.data import NapcatData
from bilipy_bot.sources.napcat.api import NapcatApi
from bilipy_bot.sources.napcat.types import NapcatType

_log = getLogger("NapcatSource")


class NapcatSource(BaseSource):
    """Napcat 事件源.

    使用 WebSocket 协议连接 NapCat 服务器，接收并发布事件。
    """

    supported_types = NapcatType

    def __init__(self, config_key: str = "napcat"):
        """初始化 Napcat 事件源.

        Args:
            config_key: 配置键，默认"napcat"
        """
        super().__init__()  # 必须调用
        self.config_key = config_key

    async def _process_messages(self, message: dict[str, Any]) -> None:
        """处理接收到的消息.

        Args:
            message: 原始消息字典
        """
        napcat_type = NapcatType.get_specific_type(message)
        event: Optional[Event] = None

        try:
            # 使用 BaseDataModel 的自动分发构造
            napcat_event = NapcatData.from_dict(message)

            if napcat_type.matches(NapcatType.ALL):
                event = Event(data=napcat_event, status=napcat_type)
            else:
                _log.warning("未处理的消息类型: %s", napcat_type)
        except Exception as e:
            _log.error("解析消息失败: %s, 原始消息: %s", e, message)
            return

        if event is not None:
            await self.ctx.bus.publish(self.uuid, event)

    async def start(self) -> None:
        """启动事件源."""
        self.api.set_handler(self._process_messages)
        await self.api.start()

    async def stop(self) -> None:
        """停止事件源."""
        await self.api.stop()

    @property
    def api(self) -> NapcatApi:
        """获取 NapcatApi 实例."""
        return self.ctx.api_ctx.get(NapcatApi, self.config_key)
```

------

## 使用方式

### 基本使用

```python
from bilipy_bot.core import BotApp, RuntimeConfig
from bilipy_bot.sources.napcat import NapcatSource, NapcatConfig

# 创建配置
config = RuntimeConfig(
    napcat=NapcatConfig(url="ws://localhost:3001"),
)

# 创建应用
app = BotApp(config)

# 添加事件源
source = app.add_source(NapcatSource)
source_id = source.uuid

# 订阅事件
from bilipy_bot.sources.napcat import NapcatType
from bilipy_bot.sources.napcat.data import NapcatGroupMessageData
from bilipy_bot.sources.napcat.events import NapcatGroupMessageEvent

@app.subscribe(source_id, NapcatType.MESSAGE, event_filter=GroupFilter(123456))
async def handle_message(event: NapcatGroupMessageEvent):
    data = event.data
    if isinstance(data, NapcatGroupMessageData):
        print(f"收到群消息: {data.message.plain_text}")

# 启动应用
import asyncio
asyncio.run(app.start())
```

### 异步上下文管理器

```python
import asyncio
from bilipy_bot.core import BotApp, RuntimeConfig
from bilipy_bot.sources.napcat import NapcatSource, NapcatConfig

async def main():
    config = RuntimeConfig(
        napcat=NapcatConfig(url="ws://localhost:3001"),
    )

    async with BotApp(config) as app:
        source = app.add_source(NapcatSource)

        @app.subscribe(source.uuid, NapcatType.ALL)
        async def handle_all(event):
            print(f"收到事件: {event.status}")

        # 保持运行
        await asyncio.Event().wait()

asyncio.run(main())
```

------

## 参考实现

- [napcat_source](../bilipy_bot/sources/napcat/source/napcat_source.py)：NapCat 事件源实现
- [bilibili_dynamic_source](../bilipy_bot/sources/bilibili/source/bili_dynamic_source.py)：B站动态事件源
- [bilibili_live_source](../bilipy_bot/sources/bilibili/source/bili_live_source.py)：B站直播事件源
- [bilibili_danmaku_source](../bilipy_bot/sources/bilibili/source/bili_danmaku_source.py)：B站弹幕事件源
