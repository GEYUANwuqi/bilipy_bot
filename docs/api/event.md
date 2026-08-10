---
title: Event
---

# Event

导入：

```python
from butterbot.app import Event
```

```python
Event(data: T, status: BaseType, id: str = <自动生成>)
```

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `data` | `T` | 事件携带的领域数据 |
| `status` | `BaseType` | 事件状态 |
| `id` | `str` | 默认生成的唯一事件标识 |

`Event` 是可变泛型 dataclass。它不会自动验证 `data` 与泛型参数是否一致。
