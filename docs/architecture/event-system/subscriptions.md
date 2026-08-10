---
title: 订阅系统
---

# 订阅系统

订阅在注册期根据 Source 的 `supported_types` 编译成
`source UUID → concrete status → subscribers` 派发表。字符串和正则使用
`fullmatch`；没有任何具体状态匹配时立即抛出 `SubscriptionError`。

每次注册产生一个 `SubscriptionHandle`。即使一条通配规则展开成多个状态，它仍是
一次订阅，可以按句柄精确撤销；扩展还可以通过 `owner_id` 成组撤销并排空自己的
回调。

应用代码通常通过 `BotApp.subscribe()` 注册，底层扩展才直接操作 EventBus。用法见
[订阅与过滤](/features/subscriptions.md)，公开对象见
[Subscriber API](/api/subscriber.md) 和 [subscribe API](/api/subscribe.md)。
