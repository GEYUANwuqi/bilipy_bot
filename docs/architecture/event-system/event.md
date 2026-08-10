---
title: Event
---

# Event

`Event[T]` 是事件系统的最小传输单元，由 `data`、`status` 和自动生成的 `id`
组成。`data` 承载领域数据，`status` 必须是 `BaseType` 成员；泛型只描述静态类型，
运行时数据校验应在创建 Data 对象时完成。

事件源只负责构造并发布事件，不直接调用业务处理器：

```python
event = Event(data=payload, status=MyType.READY)
await self.ctx.bus.publish(self.uuid, event)
```

公开字段和构造签名见 [Event API](/api/event.md)。
