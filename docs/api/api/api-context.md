---
title: APIContext
---

# APIContext

公开类型名是 `ApiRegistry`，通过 `AppContext.api_ctx` 使用：

```python
api = ctx.api_ctx.get_api(MyApi, "account")
config = ctx.api_ctx.require_config("account")
```

| 方法 | 说明 |
| --- | --- |
| `get_api(cls, config_key)` / `get(...)` | 获取或创建按类和配置键缓存的实例 |
| `require_config(config_key)` | 获取必需配置，缺失时抛 `ConfigError` |
| `aclose_all()` | 关闭并清空所有缓存实例 |
| `clear()` | 仅清缓存，主要用于测试，不释放连接 |

`AppContext` 还公开只读属性 `config`、`api_ctx` 和 `bus`。
