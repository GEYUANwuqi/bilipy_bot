---
title: 过滤与匹配机制
---

# 过滤与匹配机制

状态匹配先在注册期决定“哪些事件可能进入回调”；`BaseFilter.check(event)` 再在回调
task 内同步决定“当前事件是否通过”。两层过滤职责不同。

`BaseFilter` 可通过 `&` 和 `|` 组合为 `AndFilter`、`OrFilter`。组合按传入顺序短路，
因此应把便宜、选择性高的检查放在前面。Filter 不应执行网络 I/O 或其他异步工作。

扩展写法见 [自定义 Filter](/extensions/custom-filter.md)，稳定接口见
[BaseFilter](/api/filter/base-filter.md) 和
[CombinedFilter](/api/filter/combined-filter.md)。
