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
  - [WS 连接底层模块](../utils/wsclient.py) (/utils/wsclient.py)

### Data层

- [napcat_data 模块](data/__init__.py)
  - 对 napcat 接口返回的原始数据的封装
  - 从 napcat 源码提出事件的原始结构
    - 使用本模块的 [BaseDataModel](../base_cls/base_model.py) 进行数据验证，封装和分发

### Source层

- [napcat_source 模块](source/napcat_source.py)
  - 需要注意的是，由于 WS/API层 已经足够完善，所以这个事件源仅仅承担粘合和分发事件的作用，并没有过多的业务逻辑

### Type层

- [napcat_type 模块](type/napcat_type.py)
  - 定义了napcat事件源的(第一层路由)类型枚举类，例如消息事件类、请求事件类等

------

## 配置说明

### 运行时配置

```python
from manager import SourceManager, RuntimeConfig
from napcat import NapcatConfig

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
from napcat import NapcatSource

napcat_source = manager.add_source(
    source_cls=NapcatSource,
)
napcat_id = napcat_source.uuid
```

1. `uuid(str)`是事件源的唯一标识符，用于订阅事件

### 事件订阅

```python
from napcat import NapcatType
from napcat.data import NapcatGroupMessageEvent, NapcatPrivateMessageEvent
from event import Event

@manager.subscribe(napcat_id, NapcatType.MESSAGE)
async def handle_group_message(event: Event[NapcatGroupMessageEvent | NapcatPrivateMessageEvent]):
    """处理所有消息（群消息和私聊消息）"""
    data = event.data

    if isinstance(data, NapcatGroupMessageEvent):
        # 提取纯文本内容
        plain_text = data.message.plain_text
        sender_name = data.sender.card or data.sender.nickname
        _log.info(f"[群消息] 群 {data.group_id} - {sender_name}: {plain_text}")

    elif isinstance(data, NapcatPrivateMessageEvent):
        plain_text = data.message.plain_text
        _log.info(f"[私聊消息] {data.sender.nickname} ({data.user_id}): {plain_text}")
```

1. `NapcatType.MESSAGE` 是第一层路由类型枚举类，表示所有消息事件（包括群消息和私聊消息）
2. 事件处理函数接收一个 `Event` 对象，`event.data` 的类型可以是 `NapcatGroupMessageEvent` 或 `NapcatPrivateMessageEvent`，根据事件类型进行区分处理
3. 通过 `data.message.plain_text` 可以获取消息的纯文本内容，通过 `data.sender` 可以获取发送者的信息，例如昵称、用户ID等

------

## 完整运行示例

- [napcat](../napcat_example.py)：napcat事件监听

------

## 参考链接

- [NapcatQQ](https://github.com/NapNeko/NapCatQQ)
- [NapcatQQ-docs](https://napneko.github.io/guide/start-install)