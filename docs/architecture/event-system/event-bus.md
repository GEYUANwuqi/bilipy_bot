---
title: EventBus
---

# EventBus

`EventBus` 保存订阅派发表，并为每次匹配创建独立的回调 task。`publish()` 负责完成
派发，不承诺等待业务回调结束；总线持有 task 强引用，并在 `close()` 时统一排空。

可用 `max_pending_callbacks` 限制整个总线的 in-flight 回调数。容量耗尽时发布方会
等待，从而把背压传回事件源。事件源不应再用无界 `create_task()` 包装
`publish()`，否则会绕过这层约束。

关闭顺序是：拒绝新事件、等待已有回调、取消超时回调、等待取消完成。回调异常由
总线记录，不回传给发布方。

方法签名见 [EventBus API](/api/event-bus.md)。
