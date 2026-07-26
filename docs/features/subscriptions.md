---
title: 订阅与过滤
---

# 订阅与过滤

## 本页目标

为已注册 Source 添加异步 Handler，并选择合适的状态和内容过滤方式。

## 基本订阅

```python
source = app.add_source(NapcatSource)


@app.subscribe(source.uuid, NapcatType.GROUP_MESSAGE)
async def on_group_message(event: NapcatGroupMessageEvent) -> None:
    print(event.data.message.plain_text)
```

`source.uuid` 隔离同类型的不同实例，`status` 决定哪些状态进入 Handler。

## 状态的三种写法

```python
import re

# 枚举成员；父级 MESSAGE 会匹配 group/private 子状态。
app.subscribe(source.uuid, NapcatType.MESSAGE)

# 字符串会作为正则，并通过 re.fullmatch 匹配完整状态值。
app.subscribe(source.uuid, r"napcat\.message\..*")

# 预编译正则。
pattern = re.compile(r"napcat\.(message|notice)\..*")
app.subscribe(source.uuid, pattern)
```

装饰器仍需要作用于函数；上面的调用只展示 `status` 参数形式。
规则注册时会针对 `source.supported_types` 展开。零匹配立即抛
`SubscriptionError`。

## 内容过滤

NapCat 提供以下同步过滤器：

| 过滤器 | 参数 | 通过条件 |
| --- | --- | --- |
| `GroupFilter` | `*group_ids: int` | `event.data.group_id` 在列表中 |
| `UserFilter` | `*user_ids: int` | `event.data.user_id` 在列表中 |
| `SenderRoleFilter` | `owner/admin/member` | 群消息发送者角色匹配 |
| `TextFilter` | 关键词、`case_sensitive=False` | 文本包含任一关键词 |
| `CommandFilter` | 完整命令 | 第一个空白分隔项精确匹配 |
| `PrefixFilter` | 前缀 | 文本以任一前缀开头 |

```python
from bilipy_bot.sources.napcat.filters import CommandFilter, GroupFilter

admin_help = GroupFilter(123456) & CommandFilter("/help")


@app.subscribe(
    source.uuid,
    NapcatType.GROUP_MESSAGE,
    event_filter=admin_help,
)
async def on_help(event: NapcatGroupMessageEvent) -> None:
    ...
```

`&` 和 `|` 按传入顺序短路。事件缺少目标字段时，NapCat 预置过滤器默认拦截。

## 手动注册与取消

```python
app.add_subscriber(source.uuid, on_group_message, NapcatType.GROUP_MESSAGE)
removed = app.unsubscribe(source.uuid)
```

`unsubscribe()` 会删除该 Source UUID 的全部订阅，并返回派发表中移除的回调数。
它不会停止 Source，也不会取消已经开始执行的 Handler。

## 限制与误用

- Handler 必须是协程函数；
- Filter 的 `check()` 是同步函数，不适合执行网络请求；
- `publish()` 不等待 Handler 完成；
- 同一个 Handler 通过通配规则展开到多个状态时，取消计数按状态项计算；
- 普通字符串是正则，不是自动转义的字面量。

## 相关页面

- [事件、状态与处理器](/concepts/events-and-handlers.html)
- [开发自定义 Filter](/extensions/filters.html)
- [订阅故障排除](/troubleshooting/runtime.html)
