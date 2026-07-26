---
title: RuntimeConfig
---

# RuntimeConfig

## 构造与读取

```python
from butter_bot.app import RuntimeConfig

config = RuntimeConfig(
    service={"endpoint": "http://localhost"},
    retries=3,
)

assert config.get_config("retries") == 3
assert config.get_config("missing") is None
assert config.get_config("missing", 10) == 10
```

构造器接受任意关键字参数，不执行字段校验。具体对象的验证应由调用方或
YAML builder 负责。

## 公共项

框架没有全局固定配置 schema。当前内置 Source 使用以下顶层键：

| 名称 | 运行时类型 | 必填 | 默认值 | 使用者 |
| --- | --- | --- | --- | --- |
| `napcat` | `NapcatConfig` | 使用 NapCat 时必填 | 无 | `NapcatApi` |
| `bilibili` | `Credential` 或 `None` | 取决于 Source/API | 无 | `BilibiliApi` |

自定义扩展可以使用自己的键，通常让 Source 的 `config_key` 与 YAML 顶层键一致。

## `config_key`

`BaseSource.config_key` 决定 Source 从哪个配置键获取 API：

```python
source_a = app.add_source(NapcatSource, config_key="napcat_a")
source_b = app.add_source(NapcatSource, config_key="napcat_b")
```

此时应构造包含两个 `NapcatConfig` 的 `RuntimeConfig`。内置 YAML builder
只按精确键名 `napcat` 自动转换；自定义键需要手工构造配置，或为每个键注册
builder。

## 自定义 Provider

core 的 `AppContext` 接受实现 `ConfigProvider` Protocol 的对象，但 `BotApp`
的 `config` 参数类型是 `RuntimeConfig`。需要完全替换 provider 时，应显式构造
`AppContext` 并注入 `BotApp`。

## 限制

- 不支持嵌套点号访问；
- 不合并多个文件；
- 不自动读取环境变量；
- 不隐藏或加密敏感值；
- `get_config()` 对缺失键默认静默返回 `None`；API 可用
  `ApiRegistry.require_config()` 获得明确 `ConfigError`。
