---
title: 开发 Filter
---

# 开发 Filter

## 契约

继承 `BaseFilter` 并同步实现 `check(event) -> bool`：

```python
from butter_bot.app import BaseFilter, Event


class MinimumValueFilter(BaseFilter):
    def __init__(self, minimum: int) -> None:
        self.filters = minimum

    def check(self, event: Event) -> bool:
        value = getattr(event.data, "value", None)
        return isinstance(value, int) and value >= self.filters
```

`filters` 用于 `repr` 和调试，可保存实际过滤参数。

## 注册与组合

```python
event_filter = MinimumValueFilter(10) & EnabledFilter()


@app.subscribe(source.uuid, MyType.VALUE, event_filter=event_filter)
async def on_value(event: Event[ValueData]) -> None:
    ...
```

`AndFilter` 遇到第一个 `False` 停止；`OrFilter` 遇到第一个 `True` 停止。链式组合
会形成嵌套过滤器，但保持从左到右求值。

## 设计建议

- 缺少目标字段时返回 `False`，不要抛 `AttributeError`；
- 保持同步、快速且无网络 I/O；
- 不修改 Event 或 Data；
- 对空文本、`None` 和错误类型写边界测试；
- 把命令精确匹配与前缀匹配拆成不同 Filter，避免语义含糊。

## 异常行为

Filter 在 EventBus 创建的 Handler wrapper 中执行。`check()` 抛异常会让该
Handler task 失败并记录日志，原 Handler 不会执行；异常不会回传给 Source 的
`publish()`。

## 测试

Filter 通常不需要真实事件循环。直接构造 `Event` 并断言 `check()`，再增加一个
EventBus 集成测试确认未通过时 Handler 不执行。
