---
title: BaseSource
---

# BaseSource

导入：

```python
from butterbot.core.source import BaseSource
```

子类必须声明 `supported_types`，并实现 `on_start()`、`on_stop()`。常用公开成员：

| 成员 | 说明 |
| --- | --- |
| `uuid` | Source 唯一标识 |
| `source_kind` | 可选逻辑类型 |
| `config_key` | API 配置实例键 |
| `supported_types` | 支持的 `BaseType` 枚举类 |
| `ctx` | 绑定后的 `AppContext` |
| `state` / `health` | 生命周期与健康快照 |
| `start()` / `stop()` | 幂等模板方法，子类不应覆写 |
| `on_start()` / `on_stop()` | 子类生命周期钩子 |

`bind()` 由 `SourceManager` 调用。以下划线开头的健康上报 helper 是实现细节，不属于
稳定公开 API。
