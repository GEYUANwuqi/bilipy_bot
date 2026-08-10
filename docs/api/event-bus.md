---
title: EventBus
---

# EventBus

导入：

```python
from butterbot.core.event import EventBus
```

```python
EventBus(*, max_pending_callbacks: int | None = None)
```

稳定成员：

| 成员 | 说明 |
| --- | --- |
| `closed` | 总线是否已拒绝新发布 |
| `pending_callbacks` | 尚未完成的回调数量 |
| `max_pending_callbacks` | 回调 task 容量上限 |
| `add_subscriber(...)` | 注册协程回调并返回 `SubscriptionHandle` |
| `subscribe(...)` | 返回订阅装饰器 |
| `publish(uuid, event)` | 派发事件，不等待本次业务回调结束 |
| `remove_subscription(handle)` | 精确撤销一次订阅 |
| `remove_subscribers(uuid)` | 撤销某 Source 的全部订阅 |
| `remove_subscribers_by_owner(owner_id)` | 撤销某所有者的订阅 |
| `drain_owner(owner_id, timeout=5.0)` | 排空某所有者已开始的回调 |
| `close(timeout=5.0)` | 停止派发并排空总线 |

`max_pending_callbacks` 必须为正整数或 `None`。总线关闭后再次发布不会产生新回调。
