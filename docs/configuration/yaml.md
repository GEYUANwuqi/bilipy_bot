---
title: YAML 配置
---

# YAML 配置

## 加载

```python
from butterbot.app import RuntimeConfig

config = RuntimeConfig.from_yaml("config.yaml")
```

省略路径时读取当前工作目录的 `config.yaml`。`BotApp()` 没有收到 `config`
参数时会自动执行这一加载。加载顺序为：

1. 使用 `yaml.safe_load()` 读取文件；
2. 合并 YAML `environment` 和当前进程环境；
3. 递归解析字符串中的环境变量引用；
4. 应用 `BUTTERBOT__` 分层环境变量覆盖；
5. 按 `source_name` 调用 builder。

## 命名 Source 配置

推荐把 Source 配置放在 `sources` 下：

```yaml
sources:
  bili_account:
    source_name: bilibili
    sessdata: ""
    bili_jct: ""
    buvid3: ""

  qq_account:
    source_name: napcat
    url: "ws://localhost:3001"
    token: ""
```

`bili_account` 和 `qq_account` 是用户定义的实例键，会直接成为运行时
`config_key`。`source_name` 是配置类型或平台名，用来选择 builder；它不会传给
builder，也不会自动创建 Source。

```python
from butterbot.app import BotApp
from butterbot.sources.napcat import NapcatSource

app = BotApp()
source = app.add_source(NapcatSource, config_key="qq_account")
```

同一 `source_name` 可以构建多个命名配置，适合多账号或多端点：

```yaml
sources:
  qq_primary:
    source_name: napcat
    url: "ws://localhost:3001"
  qq_backup:
    source_name: napcat
    url: "ws://localhost:3002"
```

`sources` 必须是映射；每个实例也必须是映射，并包含非空字符串
`source_name`。实例键不能和 YAML 的其他顶层配置键重名。

普通应用配置仍可放在顶层并保留 YAML 解析后的原始值。但已注册的 builder 名称
不能作为顶层键；例如顶层 `napcat:` 或 `bilibili:` 会直接抛 `ConfigError`，
必须移入 `sources` 并显式填写 `source_name`。

## 内置 builder

### `napcat`

构建 `NapcatConfig`：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | `str` | 是 | 无 | WebSocket 地址 |
| `token` | `str \| null` | 否 | `null` | Authorization 值 |
| `heartbeat` | `float` | 否 | `30.0` | 客户端心跳间隔（秒） |
| `reconnect_attempts` | `int` | 否 | `5` | 重连尝试次数 |
| `receive_timeout` | `float` | 否 | `60.0` | 接收与请求等待超时（秒） |

### `bilibili`

把移除 `source_name` 后的映射作为关键字参数传给
`bilibili_api.Credential`。可用字段由当前锁定的
`bilibili-api-python` 决定，仓库模板列出 `sessdata`、`bili_jct` 和 `buvid3`。

## 注册自定义 builder

```python
from dataclasses import dataclass

from butterbot.app import RuntimeConfig, register_builder


@dataclass
class FeedConfig:
    endpoint: str
    interval: float = 30.0


def build_feed(value: dict) -> FeedConfig:
    return FeedConfig(**value)


register_builder("feed", build_feed)
config = RuntimeConfig.from_yaml("config.yaml")
```

对应 YAML：

```yaml
sources:
  primary_feed:
    source_name: feed
    endpoint: "https://example.com/feed"
    interval: 60
```

默认 builder registry 是进程级状态，同名注册默认抛 `ConfigError`。注册返回
`BuilderRegistration`，可用 `unregister()` 精确撤销；明确替换时必须传
`replace=True`。测试和扩展原型优先使用
`ConfigBuilderRegistry.with_defaults()` 创建隔离副本，再通过
`RuntimeConfig.from_yaml(builder_registry=registry)` 加载。

配置构建完成后，`RuntimeConfig.source_definitions` 会保留每个实例的
`config_key`、`source_name` 和构建结果。`source_name` 仍只代表配置构建器，
不等同于具体事件流的 `SourceRef.source_kind`。

builder 抛出的普通异常会包装为 `ConfigError` 并保留 cause。

## 错误

| 现象 | 异常 |
| --- | --- |
| 文件不存在 | `FileNotFoundError` |
| YAML 语法错误 | `yaml.YAMLError` |
| 顶层、`sources` 或实例结构错误 | `ConfigError` |
| `source_name` 缺失或没有注册 | `ConfigError` |
| 环境变量缺失、引用循环或覆盖路径冲突 | `ConfigError` |
| builder 构建失败 | `ConfigError` |

## 安全

复制模板后只在本地填写默认值：

```bash
cp examples/config.example.yaml config.yaml
```

生产环境优先使用环境变量注入 Secret。不要把实际配置粘贴到日志、Issue 或文档。
仓库忽略根目录 `/config.yaml`，但其他位置的同名文件不一定被忽略，提交前仍需检查
`git status`。
