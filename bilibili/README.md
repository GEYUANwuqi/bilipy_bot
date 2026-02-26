# Bilibili事件源说明文档

> 本文档介绍了bilibili事件源的使用方法和相关信息。<br>
> 注：本事件源的底层实现基于 [bilibili-api-python库](https://github.com/nemo2011/bilibili-api)

------

## 基础设施

### API层

- [bili_api 模块](api/bili_api.py)
  - 对 bilibili-api 库接口的封装，提供了获取动态/直播信息等功能

### Data层

- [bili_data 模块](data/__init__.py)
  - 对 bilibili-api 库接口返回的原始数据的封装
  - 定义了事件源相关的数据类，例如动态信息类、直播信息类等

### Source层

- [bili_source 模块](source/__init__.py)
  - 目前已有的事件源类：
    - `BiliDynamicSource`：基于轮询的B站动态事件源
    - `BiliLiveSource`：基于轮询的B站直播事件源
    - `BiliLiveDanmakuSource`：基于 WebSocket 的B站直播弹幕事件源

### Type层

- [bili_type 模块](type/bili_type.py)
  - 定义了事件源相关的 type 枚举类，例如动态事件类、直播事件类等

------

## 配置说明

### 运行时配置

```python
from manager import SourceManager, RuntimeConfig
from bilibili_api import Credential

credential = Credential(
    sessdata="",
    bili_jct="",
    buvid3=""
)

# 创建运行时配置
config = RuntimeConfig(
    bilibili=credential,  # 参数名必须为"bilibili"，值为Credential实例
)

# 创建管理器
manager = SourceManager(config)
```

1. 首先从bilibili_api库中导入Credential类，并创建一个Credential实例，并填入cookie信息
2. 创建一个RuntimeConfig实例，并将Credential实例作为名为"bilibili"的参数传入
3. 创建SourceManager实例，并将RuntimeConfig实例传入

> 关于cookie参数的获取方法可以参考 [bilibili-api-python 文档](https://nemo2011.github.io/bilibili-api/#/get-credential)

### 添加事件源

```python
from bilibili import BiliDynamicSource, BiliLiveSource

# 添加动态轮询事件源
dynamic_source = manager.add_source(
    source_cls = BiliDynamicSource,
    watch_targets = [1802011210],  # 用户uid
    poll_interval=100  # 轮询间隔，单位为秒
)
dynamic_id = dynamic_source.uuid

live_source = manager.add_source(
    source_cls = BiliLiveSource,
    watch_targets = [22758221],  # 直播间id
    poll_interval=100  # 轮询间隔，单位为秒
)
live_id = live_source.uuid
```

1. 需要注意的是，对于额外参数，如 `watch_targets` 应保证拼写正确
2. `uuid(str)`是事件源的唯一标识符，用于订阅事件

> `watch_targets`等额外参数是事件源在`__init__`中规定的，可以参考 [动态源定义的 __init__ 方法中的额外关键字参数](source/bili_dynamic_source.py)

### 事件订阅

```python
from bilibili import DynamicType, LiveType
from bilibili.data import DynamicData, LiveRoomData
from event import Event

@manager.subscribe(dynamic_id, DynamicType.ALL)
async def handle_get_dynamic(event: Event[DynamicData]):
    """每次轮询获取动态时都会触发"""
    _log.info(f"{event.data.author.name} 的动态状态: {event.status}")

@manager.subscribe(dynamic_id, DynamicType.NEW)
async def handle_new_dynamic(event: Event[DynamicData]):
    """仅当检测到新动态时触发"""
    _log.info(f"[新动态] UP主 {event.data.author.name} 发布了新动态！")
    _log.info(event.data)

@manager.subscribe(live_id, LiveType.OPEN)
async def handle_live_open(event: Event[LiveRoomData]):
    """开播时触发"""
    name = event.data.anchor_info.name
    title = event.data.room_info.title
    room_id = event.data.room_info.room_id
    _log.info(f"[开播通知] {name} 开播了！{title} https://live.bilibili.com/{room_id}")
```

1. `@manager.subscribe` 的两个参数分别是事件源的uuid和事件类型，事件类型需要使用事件源定义的type枚举类，例如 `DynamicType` 和 `LiveType`
2. 事件处理函数需要是异步函数， `event` 参数用于事件传参 (你也可以把这个参数改成其他名字) ，可以通过注解的方式来标注 `event.data` 的类型，例如 `Event[DynamicData]` 和 `Event[LiveRoomData]`

> 如果你不想使用装饰器，也可以直接调用 `manager.add_subscriber` 方法来订阅事件，只需要多传入一个事件处理函数 `callback` 即可

------

## 完整运行示例

- [bilibili](../manager_example.py)：B站动态/直播事件监听
- [bilibili_danmaku](../live_danmaku_example.py)：bilibili直播弹幕监听

------

## 注意事项

- 从v3.0.1开始，框架不强要求事件源必须是单例，但因为风控，仍不建议创建多个轮询事件源，这是非常危险的行为，会大大增加被风控的概率
