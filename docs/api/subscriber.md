---
title: Subscriber
---

# Subscriber

导入：

```python
from butterbot.core.event import Subscriber, SubscriptionHandle
```

`Subscriber` 保存编译前的回调、状态规则、可选内容过滤器与所有者标识。
`SubscriptionHandle` 是一次注册的不透明句柄：

```python
SubscriptionHandle(
    subscription_id: UUID,
    source_id: UUID,
    owner_id: str | None = None,
)
```

业务代码通常不直接构造它们，而是接收 `EventBus.add_subscriber()` 的返回值并交给
`remove_subscription()`。`SubscriberGroup` 属于事件系统实现细节，不列入稳定 API。
