---
title: 事件、状态与处理器
---

# 事件、状态与处理器

## 类型关系

项目没有独立 `Handler` 类。Handler 是签名为
`async def callback(event: Event[Data]) -> None` 的协程函数。

`Event[T]` 是泛型 dataclass：

- `data: T` 保存领域数据；
- `status: BaseType` 保存事件状态；
- `id: str` 默认生成唯一字符串。

```python
from dataclasses import dataclass

from butterbot.app import Event
from butterbot.core.data import BaseDataMixin
from butterbot.core.types import BaseType


class JobType(BaseType):
    ALL = "job.all"
    DONE = "job.done"


@dataclass
class JobData(BaseDataMixin):
    job_id: int


event = Event(data=JobData(job_id=42), status=JobType.DONE)
```

## 注册处理器

必须先添加 Source，再注册订阅，因为 `BotApp.subscribe()` 需要读取 Source 的
`supported_types`：

```python
source = app.add_source(MySource)


@app.subscribe(source.uuid, MyType.READY)
async def on_ready(event: Event[MyData]) -> None:
    print(event.data)
```

同步函数会在注册时抛出 `TypeError`。

## 状态规则

订阅规则可以是：

- `BaseType` 成员：支持 `all` 和父级状态匹配；
- `str`：作为正则表达式执行 `re.fullmatch`；
- `re.Pattern[str]`：执行其 `fullmatch`。

规则在注册期展开为具体状态。没有任何匹配会抛出 `SubscriptionError`，避免
错误拼写变成永远不执行的静默订阅。

## 发布不是等待 Handler 完成

`await EventBus.publish(...)` 负责创建 Handler task，但默认不会等待这些 Handler
执行完。EventBus 持有强引用，并在 `close()` 时统一排空。

若 EventBus 配置了 `max_pending_callbacks`，`publish()` 在容量耗尽时会等待已有
Handler 完成。它仍不等待本次新建 Handler 的业务结果；等待只表示获得调度容量。

如果业务流程需要等待某个处理结果，应使用显式的 `asyncio.Event`、Queue 或
Future 建立同步关系，不要误以为 `publish()` 返回就代表 Handler 已完成。

## 过滤器

`event_filter` 在 Handler task 内同步调用 `check(event)`。过滤器本身不是异步
接口：

```python
@app.subscribe(source.uuid, MyType.READY, event_filter=MyFilter())
async def on_ready(event: Event[MyData]) -> None:
    ...
```

## 常见误用

- 使用同步回调；
- 在添加 Source 前订阅；
- 把普通字符串理解为字面量，而它实际是完整正则；
- 假设 `publish()` 等待所有处理器完成；
- 在 Handler 中创建长期任务但不保存、取消和等待它。

## 相关页面

- [订阅与过滤](/features/subscriptions.md)
- [BaseType API](/api/core.md)
- [并发与任务所有权](./concurrency.md)
