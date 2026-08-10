---
title: BaseFilter
---

# BaseFilter

导入：

```python
from butterbot.app import BaseFilter
```

子类必须实现同步方法：

```python
def check(self, event: Event) -> bool: ...
```

返回 `True` 表示事件通过。`filter_a & filter_b` 和 `filter_a | filter_b` 分别创建与、
或组合过滤器。Filter 在 EventBus 回调 task 内执行，不支持 `async def check()`。
