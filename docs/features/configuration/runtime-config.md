---
title: RuntimeConfig
---

# RuntimeConfig

## 构造与读取

```python
from butterbot.app import RuntimeConfig

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

框架没有全局固定配置 schema。YAML 中每个命名 Source 配置会以自定义实例键存入
`RuntimeConfig`：

| `source_name` | 运行时类型 | 必填 | 使用者 |
| --- | --- | --- | --- |
| `napcat` | `NapcatConfig` | 使用 NapCat 时必填 | `NapcatApi` |
| `bilibili` | `Credential` | 取决于 Source/API | `BilibiliApi` |
| `lark` | `LarkConfig` | 使用飞书时必填 | `LarkApi` |

已注册的 builder 名称不能作为 YAML 顶层键。Source 配置必须放在 `sources`
下，普通应用配置仍可使用顶层键并以原始值存储。

## `config_key`

`BaseSource.config_key` 决定 Source 从哪个配置键获取 API：

```python
source_a = app.add_source(NapcatSource, config_key="napcat_a")
source_b = app.add_source(NapcatSource, config_key="napcat_b")
```

对应 YAML：

```yaml
sources:
  napcat_a:
    source_name: napcat
    kwarg:
      NapcatSource: {}
    url: "ws://localhost:3001"
  napcat_b:
    source_name: napcat
    kwarg:
      NapcatSource: {}
    url: "ws://localhost:3002"
```

自定义实例键是 `config_key`；`source_name` 只负责选择 builder。可选的
`kwarg.<SourceClassName>` 才选择并配置需要自动创建的具体 Source。使用上述 YAML
时，`BotApp()` 已经注册两个实例，可直接通过
`app.get_source(NapcatSource, "napcat_a")` 获取。

开头的两行 `add_source()` 仍是受支持的等价手动组装方式；要使用它们，只需从
YAML 删除 `kwarg`，避免同时声明和手动添加同一逻辑实例。

## 自定义 Provider

core 的 `AppContext` 接受实现 `ConfigProvider` Protocol 的对象，但 `BotApp`
的 `config` 参数类型是 `RuntimeConfig`。需要完全替换 provider 时，应显式构造
`AppContext` 并注入 `BotApp`。

## 限制

- 不支持嵌套点号访问；
- 不合并多个文件；
- `RuntimeConfig()` 本身不读取环境变量，只有 `from_yaml()` 会读取；
- 不隐藏或加密敏感值；
- `RuntimeConfig.from_yaml()` 只校验并保存 `kwarg`，具体工厂解析和实例化发生在
  `BotApp` 构造时；
- `get_config()` 对缺失键默认静默返回 `None`；API 可用
  `ApiRegistry.require_config()` 获得明确 `ConfigError`。
