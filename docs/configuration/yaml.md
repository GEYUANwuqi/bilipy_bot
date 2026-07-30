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
5. 分离可选的 `kwarg`，再按 `source_name` 调用配置 builder；
6. `BotApp` 按 `kwarg` 中出现的 Source 类名自动实例化并注册事件源。

实验插件模式必须改用 `PluginBootstrap`。它先读取同一份已合并配置中的
`plugins.enabled`、`plugins.local` 和插件私有配置，在第 5 步前登记插件
builder、在第 6 步前登记插件 factory，随后才执行运行阶段注册。
`RuntimeConfig.from_yaml()` 本身不会发现或导入插件。

## 实验插件设置

`plugins` 是 bootstrap 保留段，不会出现在
`RuntimeConfig.get_config("plugins")` 中：

```yaml
plugins:
  enabled:
    - local.hello
    - example.feed
    - example.handler

  local:
    path: "./plugins"
    auto_enable: false

  config:
    local.hello:
      greeting: "${HELLO_GREETING:-hello}"
```

候选可来自已安装的 `butterbot.plugins` entry point，或本地
`plugins/<folder>/plugin.toml`。默认只导入 `enabled` 中的候选；
`local.auto_enable: true` 会显式选择本地目录中的全部合法候选。

相对 `local.path` 以配置文件父目录为基准。本地目录不存在且没有自动启用时视为空；
存在的无效 manifest 即使未启用也会使 `check` 和 `run` 失败。框架不修改
`sys.path`，不跟随符号链接，也不自动安装依赖。

`plugins.config` 的每个值必须是 mapping，只读注入对应插件，不进入
`RuntimeConfig`。引用未发现 plugin ID 的私有配置会直接报错。未知字段、重复 ID、
缺失候选、版本不兼容和依赖错误都会使配置无效。分层环境覆盖同样适用：

```bash
export BUTTERBOT__PLUGINS__ENABLED='[example.feed, example.handler]'
```

完整的打包、应用 factory 和信任边界见
[实验性插件系统](/extensions/plugins.html)。

## 命名 Source 配置

推荐把 Source 配置放在 `sources` 下：

```yaml
sources:
  bili_account:
    source_name: bilibili
    kwarg:
      BiliDanmakuSource:
        room_id: [26498147, 22758221]
    sessdata: ""
    bili_jct: ""
    buvid3: ""

  qq_account:
    source_name: napcat
    kwarg:
      NapcatSource: {}
    url: "ws://localhost:3001"
    token: ""
```

`bili_account` 和 `qq_account` 是用户定义的实例键，会直接成为运行时
`config_key`。`source_name` 是配置类型或平台名，用来选择 builder；它不会传给
builder，也不会被当作具体 Source 类。

```python
from butterbot.app import BotApp
from butterbot.sources.napcat import NapcatSource

app = BotApp()
source = app.get_source(NapcatSource, "qq_account")
assert source is not None
```

### `kwarg` 自动注册语法糖

`kwarg` 是 `Source 类名 -> 构造关键字参数` 映射。出现某个类名表示创建一个该类
实例；`{}` 表示创建不需要额外参数的 Source。外层实例键会自动作为
`config_key` 注入，因此不能在 `kwarg` 中重复设置：

```yaml
sources:
  bili_account:
    source_name: bilibili
    kwarg:
      BiliDynamicSource:
        watch_targets: [1802011210]
        poll_interval: 60
      BiliLiveSource:
        watch_targets: [22758221]
        poll_interval: 20
    sessdata: ""
    bili_jct: ""
    buvid3: ""
```

`BotApp()` 构造时只完成实例化和注册，不启动 Source；订阅仍可在
`app.start()` 或 `app.run()` 前安全注册。内置工厂如下：

| `source_name` | `kwarg` 可用类名 |
| --- | --- |
| `bilibili` | `BiliDanmakuSource`、`BiliDynamicSource`、`BiliLiveSource` |
| `napcat` | `NapcatSource` |

`kwarg` 完全可选。没有它时不会自动创建任何 Source，原有
`app.add_source(SourceClass, ..., config_key=...)` 用法和运行期动态接入流程均
保持不变。

插件应使用 `register_factory(..., factory_id="source")` 声明稳定 ID，YAML 使用
`kwarg.source`，而不是依赖 Python 类名：

```yaml
sources:
  primary:
    source_name: example
    kwarg:
      source: {}
```

内置 Source 类名继续作为兼容配置协议。

同一 `source_name` 可以构建多个命名配置，适合多账号或多端点：

```yaml
sources:
  qq_primary:
    source_name: napcat
    kwarg:
      NapcatSource: {}
    url: "ws://localhost:3001"
  qq_backup:
    source_name: napcat
    kwarg:
      NapcatSource: {}
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

把移除 `source_name` 和 `kwarg` 后的映射作为关键字参数传给
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
`config_key`、`source_name`、`kwarg` 和构建结果。`source_name` 仍只代表配置
构建器，不等同于具体事件流的 `SourceRef.source_kind`。

自定义 Source 可使用隔离工厂注册表：

```python
from butterbot.app import BotApp, SourceFactoryRegistry

source_registry = SourceFactoryRegistry.with_defaults()
registration = source_registry.register(
    "feed",
    FeedSource,
    factory_name="source",
    owner_id="example.feed",
)
app = BotApp(config, source_factory_registry=source_registry)
```

YAML 中即可使用 `kwarg.source`。省略 `factory_name` 时兼容使用工厂的
`__name__`。重复注册同一个 `source_name + factory_name` 会抛 `ConfigError`；
返回的 `FactoryRegistration` 可用 `unregister()` 精确撤销，旧收据不能误删后来
替换的注册。

builder 抛出的普通异常会包装为 `ConfigError` 并保留 cause。

## 错误

| 现象 | 异常 |
| --- | --- |
| 文件不存在 | `FileNotFoundError` |
| YAML 语法错误 | `yaml.YAMLError` |
| 顶层、`sources` 或实例结构错误 | `ConfigError` |
| `plugins` 保留段或启用列表结构错误 | `ConfigError` |
| `source_name` 缺失或没有注册 | `ConfigError` |
| `kwarg` 或某个 Source 参数不是映射 | `ConfigError` |
| `kwarg` 指向未注册工厂或构造失败 | `BotApp` 构造时抛 `ConfigError` |
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
