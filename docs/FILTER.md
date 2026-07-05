# 过滤器说明文档

> 本文档介绍了如何编写和使用 `BaseFilter` 过滤器，以及 napcat 预置过滤器的用法。

---

## 过滤器概念

过滤器用于在**回调执行前**对事件进行内容级筛选。订阅时提供 `event_filter` 参数，只有通过过滤器的事件才会触发回调。

过滤筛选流程：

```
Source 产生数据 → EventBus.publish(uuid, Event)
    → 状态匹配（status_filter 编译展开）
        → event_filter.check(event)  ← 内容过滤
            → asyncio.create_task(callback(event))
```

---

## 使用预置过滤器

napcat 事件源提供了一组预置过滤器，可直接组合使用：

```python
from bilipy_bot.sources.napcat import NapcatType
from bilipy_bot.sources.napcat.filters import GroupFilter, TextFilter, CommandFilter

# 单一过滤器
@app.subscribe(source.uuid, NapcatType.GROUP_MESSAGE, event_filter=GroupFilter(123456))
async def handler(event):
    ...

# 组合：&（与）和 |（或）
filter = GroupFilter(123456) & TextFilter("hello")
@app.subscribe(source.uuid, NapcatType.GROUP_MESSAGE, event_filter=filter)
async def handler(event):
    ...

# 组合短路行为：A & B 中 A 不通过则不再检查 B
#              A | B 中 A 通过则不再检查 B
```

### 预置过滤器列表

| 过滤器 | 用途 | 示例 |
|---|---|---|
| `GroupFilter(*group_ids)` | 按群号过滤 | `GroupFilter(123456)` |
| `UserFilter(*user_ids)` | 按用户 ID 过滤 | `UserFilter(10001, 10002)` |
| `SenderRoleFilter(*roles)` | 按发送者角色过滤 | `SenderRoleFilter("owner", "admin")` |
| `TextFilter(*keywords, case_sensitive=False)` | 消息文本含关键词 | `TextFilter("help")` |
| `CommandFilter(*commands)` | 精确匹配完整命令 | `CommandFilter("/help", "/status")` |
| `PrefixFilter(*prefixes)` | 按消息前缀匹配 | `PrefixFilter("/")` |

> `CommandFilter` 和 `PrefixFilter` 的区别：
> - `CommandFilter("/help")` 匹配 `"/help"` 和 `"/help args"`，**不**匹配 `"/helpme"`
> - `PrefixFilter("/")` 匹配所有以 `/` 开头的消息（`"/help"`、`"/status"` 等）

---

## 编写自定义过滤器

继承 `BaseFilter` 并实现 `check` 方法：

```python
from bilipy_bot.app import BaseFilter
from bilipy_bot.core.event import Event

class MyFilter(BaseFilter):
    filters: list  # 用于 repr 显示

    def __init__(self, *args):
        self.filters = list(args)

    def check(self, event: Event) -> bool:
        """返回 True 通过，False 拦截。"""
        return condition
```

### 命名规范

- 预期只用于某事件源的过滤器，使用事件源前缀（如 napcat 预置 `GroupFilter`）
- 通用过滤器可放在 `bilipy_bot/core/filter/` 下

### 组合规则

```python
f = FilterA() & FilterB()       # A 且 B（短路）
f = FilterA() | FilterB()       # A 或 B（短路）
f = (A & B) | (C & D)           # 任意组合
```
