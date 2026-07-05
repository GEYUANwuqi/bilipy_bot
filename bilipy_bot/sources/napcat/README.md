# Napcat事件源说明文档

> 本文档介绍了 napcat 事件源的使用方法和相关信息。<br>
> 注：本事件源的底层实现基于 [NapcatQQ](https://github.com/NapNeko/NapCatQQ)

------

## 基础设施

### WS / API层

- [napcat_api 模块](api/napcat_api.py)
  - 对 napcat 接口的封装，提供了ws连接、api调用等功能
  - [WS 连接模块](api/napcat_api.py#L38)：提供了连接 napcat ws 服务器的功能，并将接收到的消息进行解析和封装
  - [API 调用模块](api/napcat_api.py#L213)：提供了调用 napcat API 的功能，例如发送消息等
  - [WS 连接底层模块](../utils/websocket.py)../utils/websocket.py)

### Data层

- [napcat_data 模块](data/__init__.py)
  - 对 napcat 接口返回的原始数据的封装
  - 从 napcat 源码提出事件的原始结构
    - 使用本模块的 [BaseDataModel](../../app/data/base_model.py) 进行数据验证，封装和分发

### Source层

- [napcat_source 模块](source/napcat_source.py)
  - 需要注意的是，由于 WS/API层 已经足够完善，所以这个事件源仅仅承担粘合和分发事件的作用，并没有过多的业务逻辑

### Event层

- [events 模块](events.py)
  - 定义了 `*Event` 类型别名（`NapcatGroupMessageEvent = Event[NapcatGroupMessageData]`），用户可直接用作类型注解
  - 分离了数据模型（`Napcat*Data`）和事件类型（`Napcat*Event`）的命名空间

### Filter层

- [filters 模块](filters/)
  - 提供预置 `BaseFilter` 子类：`GroupFilter`、`UserFilter`、`TextFilter`、`CommandFilter` 等
  - 支持 `&`（与）和 `|`（或）组合，用于回调执行前的事件内容筛选

### Type层

- [napcat_type 模块](type/napcat_type.py)
  - 定义了napcat事件源的(第一层路由)类型枚举类，例如消息事件类、请求事件类等

------

## 配置说明

### 运行时配置

```python
from bilipy_bot.core import SourceManager, RuntimeConfig
from bilipy_bot.sources.napcat import NapcatConfig

napcat_config = NapcatConfig(
    url="",  # NapCat WebSocket 地址
    token=""  # WS Token
)

# 创建运行时配置
config = RuntimeConfig(
    napcat=napcat_config,
)

# 创建管理器
manager = SourceManager(config)
```

1. `token` 和 `url` 是napcat的**WS服务端/反向WS**
2. 具体配置napcat的方法可以参考 [NapcatQQ-docs](https://napneko.github.io/config/basic)

### 添加事件源

```python
from bilipy_bot.sources.napcat import NapcatSource

napcat_source = manager.add_source(
    source_cls=NapcatSource,
)
napcat_id = napcat_source.uuid
```

1. `uuid(str)`是事件源的唯一标识符，用于订阅事件

### 事件订阅

```python
from bilipy_bot.sources.napcat import NapcatType
from bilipy_bot.sources.napcat.data import NapcatGroupMessageData, NapcatPrivateMessageData
from bilipy_bot.sources.napcat.events import (
    NapcatGroupMessageEvent,
    NapcatPrivateMessageEvent,
)

@app.subscribe(napcat_id, NapcatType.MESSAGE)
async def handle_group_message(
    event: NapcatGroupMessageEvent | NapcatPrivateMessageEvent,
):
    """处理所有消息（群消息和私聊消息）"""
    data = event.data

    if isinstance(data, NapcatGroupMessageData):
        # 提取纯文本内容
        plain_text = data.message.plain_text
        sender_name = data.sender.card or data.sender.nickname
        _log.info(f"[群消息] 群 {data.group_id} - {sender_name}: {plain_text}")

    elif isinstance(data, NapcatPrivateMessageData):
        plain_text = data.message.plain_text
        _log.info(f"[私聊消息] {data.sender.nickname} ({data.user_id}): {plain_text}")
```

1. `NapcatType.MESSAGE` 是第一层路由类型枚举类，表示所有消息事件（包括群消息和私聊消息）
2. 事件处理函数接收一个事件类型别名对象（`NapcatGroupMessageEvent` 即 `Event[NapcatGroupMessageData]`），`event.data` 的类型可以是 `NapcatGroupMessageData` 或 `NapcatPrivateMessageData`，根据事件类型进行区分处理
3. 通过 `data.message.plain_text` 可以获取消息的纯文本内容，通过 `data.sender` 可以获取发送者的信息，例如昵称、用户ID等

### 事件类型别名

`events.py`（即 `bilipy_bot.sources.napcat.events`）为每个数据模型定义了对应的类型别名，可直接用作回调的注解：

```python
from bilipy_bot.sources.napcat.events import (
    NapcatGroupMessageEvent,  # = Event[NapcatGroupMessageData]
    NapcatNoticeEvent,         # = Event[NapcatNoticeData]
    NapcatEvent,               # = Event[NapcatData]
)

@app.subscribe(source.uuid, NapcatType.GROUP_MESSAGE)
async def handler(event: NapcatGroupMessageEvent):
    # event.data 的类型自动推断为 NapcatGroupMessageData
    print(event.data.group_id)
```

用户代码中只需从 `events` 导入事件类型别名，从 `data` 导入数据模型用于 `isinstance`。

### 内容过滤器

[过滤器模块](filters/)提供预置的 `BaseFilter` 子类，可在回调执行前对事件内容进行筛选：

```python
from bilipy_bot.sources.napcat.filters import GroupFilter, TextFilter, CommandFilter

# 仅处理指定群的消息
@app.subscribe(napcat_id, NapcatType.GROUP_MESSAGE, event_filter=GroupFilter(123456))
async def handler(event):
    ...

# 组合：&（与）和 |（或）
f = GroupFilter(123456) & TextFilter("help")
@app.subscribe(napcat_id, NapcatType.GROUP_MESSAGE, event_filter=f)
async def handler(event):
    ...

# 命令精确匹配 vs 前缀匹配
f = CommandFilter("/help")     # 精确匹配 /help、/help args，不匹配 /helpme
f = PrefixFilter("/")           # 匹配任何 / 开头的消息
```

预置过滤器清单：

| 过滤器 | 用途 | 示例 |
|---|---|---|
| `GroupFilter(*group_ids)` | 按群号过滤 | `GroupFilter(123456)` |
| `UserFilter(*user_ids)` | 按用户 ID 过滤 | `UserFilter(10001)` |
| `SenderRoleFilter(*roles)` | 按发送者角色过滤 | `SenderRoleFilter("owner", "admin")` |
| `TextFilter(*keywords, case_sensitive=False)` | 消息文本含关键词 | `TextFilter("help")` |
| `CommandFilter(*commands)` | 精确匹配完整命令 | `CommandFilter("/help")` |
| `PrefixFilter(*prefixes)` | 按消息前缀匹配 | `PrefixFilter("/")` |

> 详细用法见 [FILTER.md](../../docs/FILTER.md)

------

## 完整运行示例

- [napcat](../../examples/napcat_example.py)：napcat事件监听

------

## 参考链接

- [NapcatQQ](https://github.com/NapNeko/NapCatQQ)
- [NapcatQQ-docs](https://napneko.github.io/guide/start-install)
