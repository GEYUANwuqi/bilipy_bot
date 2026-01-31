# BiliBiliManager 使用文档

## 概述

`BiliBiliManager` 是一个负责装配、生命周期和批量管理的核心类。它遵循以下设计原则：

### BiliBiliManager 只做三件事

1. **装配（Wiring）**：创建并持有 Context
2. **生命周期（Lifecycle）**：start/stop/close
3. **批量管理（Registry）**：管理多个 Source

### BiliBiliManager 不做

- ❌ 业务逻辑
- ❌ 维护订阅索引（这是 EventBus 的事）
- ❌ 直接处理 event（除非是 debug/metrics）

## 核心架构

```
BiliBiliManager
├── RuntimeConfig     # 配置源（只读）
├── APIContext        # API 单例容器
├── EventBus          # 事件总线
├── AppContext        # 统一注入对象
└── sources           # 事件源集合 dict[UUID, BaseSource]
```

## 快速开始

### 1. 创建配置和管理器

```python
from bilibili_api import Credential
from manager import BiliBiliManager
from api.context import RuntimeConfig

# B站凭证（可选）
credential = Credential(
    sessdata = "your_sessdata",
    bili_jct = "your_bili_jct",
    buvid3 = "your_buvid3"
)

# 创建运行时配置
config = RuntimeConfig(
    bilibili = credential,  # 可以传 None
)

# 创建管理器
manager = BiliBiliManager(config)
```

### 2. 创建事件源

```python
from source import BiliDynamicSource, BiliLiveSource

# 动态监控源
dynamic_source = BiliDynamicSource(poll_interval=12)
dynamic_source.add_members([621240130, 456789])  # UID 列表

# 直播监控源
live_source = BiliLiveSource(poll_interval=20)
live_source.add_members([26498147])  # 房间 ID 列表

# 注册事件源并获取 UUID
dynamic_id = manager.add_source(dynamic_source)
live_id = manager.add_source(live_source)
```

### 3. 订阅事件

使用装饰器订阅：

```python
from event import Event
from bili_data import DynamicData, LiveRoomData
from utils import DynamicType, LiveType

@manager.subscribe(dynamic_id, DynamicType.NEW)
async def on_new_dynamic(event: Event[DynamicData]):
    """检测到新动态时触发"""
    print(f"[新动态] {event.data.author.name} 发布了新动态！")

@manager.subscribe(dynamic_id, DynamicType.DELETED)
async def on_deleted_dynamic(event: Event[DynamicData]):
    """检测到删除动态时触发"""
    print(f"[删除] {event.data.author.name} 删除了动态")

@manager.subscribe(live_id, LiveType.OPEN)
async def on_live_open(event: Event[LiveRoomData]):
    """开播时触发"""
    print(f"[开播] {event.data.anchor_info.name} 开播了！")

@manager.subscribe(live_id, LiveType.CLOSE)
async def on_live_close(event: Event[LiveRoomData]):
    """下播时触发"""
    print(f"[下播] {event.data.anchor_info.name} 下播了")

@manager.subscribe(live_id, LiveType.ALL)
async def on_live_any(event: Event[LiveRoomData]):
    """所有直播状态变化时触发"""
    print(f"[直播状态] {event.status}")
```

或者使用函数式订阅：

```python
async def my_callback(event: Event):
    print(event)

manager.add_subscriber(dynamic_id, my_callback, DynamicType.NEW)
```

### 4. 启动和停止

#### 使用异步上下文管理器（推荐）

```python
import asyncio

async def main():
    async with manager:
        # BiliBiliManager 已启动，所有 Source 都在运行
        await asyncio.sleep(3600)  # 运行 1 小时
    # BiliBiliManager 已自动关闭

asyncio.run(main())
```

#### 手动控制

```python
async def main():
    await manager.start()
    try:
        await asyncio.sleep(3600)
    finally:
        await manager.stop()
        await manager.close()
```

## API 参考

### BiliBiliManager

#### 属性

| 属性 | 类型 | 描述 |
|------|------|------|
| `config` | `RuntimeConfig` | 运行时配置（只读） |
| `ctx` | `AppContext` | 应用上下文 |
| `running` | `bool` | 是否正在运行 |
| `closed` | `bool` | 是否已关闭 |
| `sources` | `dict[UUID, BaseSource]` | 所有事件源的副本 |

#### 方法

| 方法 | 描述 |
|------|------|
| `add_source(source)` | 添加事件源，返回 UUID |
| `remove_source(source_id)` | 移除事件源 |
| `get_source(source_id)` | 获取事件源 |
| `get_api(api_cls)` | 获取 API 实例 |
| `subscribe(source_id, status)` | 装饰器：订阅事件 |
| `add_subscriber(source_id, callback, status)` | 添加订阅者 |
| `start()` | 启动 BiliBiliManager |
| `stop()` | 停止 BiliBiliManager |
| `close()` | 关闭 BiliBiliManager |
| `create_task(coro)` | 创建并管理任务 |

### BaseSource

事件源基类，所有具体事件源都继承自它。

#### 属性

| 属性 | 类型 | 描述 |
|------|------|------|
| `uuid` | `UUID` | 唯一标识符 |
| `running` | `bool` | 运行状态 |
| `ctx` | `AppContext` | 应用上下文 |

#### 抽象方法

| 方法 | 描述 |
|------|------|
| `start()` | 启动事件源 |
| `stop()` | 停止事件源 |
| `add_members(keys)` | 添加监控成员 |
| `remove_members(keys)` | 移除监控成员 |

### BiliDynamicSource

B站动态事件源。

```python
source = BiliDynamicSource(poll_interval=12)
source.add_members([uid1, uid2])
source.set_poll_interval(15)
print(source.members)  # 监控的 UID 列表
print(source.poll_num)  # 已完成的轮询次数
```

### BiliLiveSource

B站直播事件源。

```python
source = BiliLiveSource(poll_interval=20)
source.add_members([room_id1, room_id2])
source.set_poll_interval(30)
print(source.rooms)  # 监控的房间 ID 列表
print(source.poll_num)  # 已完成的轮询次数
```

## 状态枚举

### DynamicType

| 值 | 描述 |
|------|------|
| `DynamicType.ALL` | 通配符，匹配所有状态 |
| `DynamicType.NEW` | 新动态 |
| `DynamicType.DELETED` | 删除的动态 |
| `DynamicType.NULL` | 无变化 |

### LiveType

| 值 | 描述 |
|------|------|
| `LiveType.ALL` | 通配符，匹配所有状态 |
| `LiveType.ONLINE` | 在线（直播中） |
| `LiveType.OFFLINE` | 离线（未开播） |
| `LiveType.OPEN` | 开播（状态变化） |
| `LiveType.CLOSE` | 下播（状态变化） |

## 生命周期

```
创建 BiliBiliManager
    │
    ▼
添加 Source（add_source）
    │
    ▼
注册订阅（subscribe / add_subscriber）
    │
    ▼
启动（start）
    ├── 为每个 Source 注入上下文（bind）
    └── 启动每个 Source
    │
    ▼
运行中...
    │
    ▼
停止（stop）
    ├── 停止每个 Source
    └── 取消所有任务
    │
    ▼
关闭（close）
    └── 清理资源
```

## 完整示例

```python
"""完整的使用示例"""
import asyncio
from bilibili_api import Credential

from manager import BiliBiliManager
from source import BiliDynamicSource, BiliLiveSource
from event import Event
from bili_data import DynamicData, LiveRoomData
from utils import LiveType, DynamicType
from api.context import RuntimeConfig

# 配置
config = RuntimeConfig(
    bilibili = Credential(sessdata = "...", bili_jct = "...", buvid3 = "...")
)

# 创建管理器
manager = BiliBiliManager(config)

# 创建事件源
dynamic_source = BiliDynamicSource(poll_interval = 12)
dynamic_source.add_members([621240130])

live_source = BiliLiveSource(poll_interval = 20)
live_source.add_members([26498147])

# 注册
dynamic_id = manager.add_source(dynamic_source)
live_id = manager.add_source(live_source)


# 订阅
@manager.subscribe(dynamic_id, DynamicType.NEW)
async def on_new_dynamic(event: Event[DynamicData]):
    print(f"新动态: {event.data.author.name}")


@manager.subscribe(live_id, LiveType.OPEN)
async def on_live_open(event: Event[LiveRoomData]):
    print(f"开播: {event.data.anchor_info.name}")


# 运行
async def main():
    async with manager:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
```
