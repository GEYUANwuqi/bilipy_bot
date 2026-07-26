---
title: 应用 API
---

# 应用 API

## `BotApp`

导入：

```python
from bilipy_bot.app import BotApp
```

签名：

```python
BotApp(
    config: RuntimeConfig | None = None,
    ctx: AppContext | None = None,
    *,
    close_timeout: float = 5.0,
)
```

`config=None` 时调用 `RuntimeConfig.from_yaml("config.yaml")`，可能抛
`FileNotFoundError`、`yaml.YAMLError` 或 `ConfigError`。

### 属性

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `config` | `RuntimeConfig` | 应用运行配置 |
| `ctx` | `AppContext` | 注入给 Source 的上下文 |
| `bus` | `EventBus` | 事件总线 |
| `api_ctx` | `ApiRegistry` | API 单例容器 |
| `manager` | `SourceManager` | Source 生命周期管理器 |
| `running` | `bool` | manager 是否运行 |
| `closed` | `bool` | manager 是否关闭 |

### Source 管理

```python
add_source(source_cls, *args, **kwargs) -> BaseSourceT
get_source(uuid) -> BaseSource | None
get_source(source_cls, config_key=None) -> BaseSourceT | None
async start_source(source_or_uuid) -> BaseSource
async stop_source(source_or_uuid) -> BaseSource
async remove_source(source_id: UUID) -> BaseSource | None
```

`add_source()` 只注册。运行期接入时调用顺序为 add、subscribe、start_source。
启动/停止未注册 Source 抛 `SourceError`；manager 关闭后添加或启动抛
`LifecycleError`。

### API

```python
get_api(api_cls: type[BaseApiT], config_key: str) -> BaseApiT
```

相同 API 类与配置键返回同一实例。构建异常原样传播。

### 订阅

```python
subscribe(
    source_id: UUID,
    status: str | re.Pattern[str] | BaseType,
    *,
    event_filter: BaseFilter | None = None,
) -> Callable

add_subscriber(
    source_id: UUID,
    callback: Callable[[Event], Coroutine[Any, Any, None]],
    status: str | re.Pattern[str] | BaseType,
    *,
    event_filter: BaseFilter | None = None,
) -> None

unsubscribe(source_id: UUID) -> int
```

Source 不存在时抛 `ValueError`。回调不是协程函数时抛 `TypeError`；状态规则无
匹配时抛 `SubscriptionError`。

### 生命周期

```python
async start() -> None
async stop() -> None
async close() -> None
run(duration: float | None = None) -> None
async __aenter__() -> BotApp
async __aexit__(exc_type, exc_val, exc_tb) -> None
```

`start()` 可能抛 `SourceStartError`。`close()` 为终态清理；`run()` 是拥有
事件循环的同步入口，内部使用 `asyncio.run()`。

## `RuntimeConfig`

导入：

```python
from bilipy_bot.app import RuntimeConfig
```

```python
RuntimeConfig(**configs: Any)
get_config(key: str, default: Any = None) -> Any
RuntimeConfig.from_yaml(path: str | Path = "config.yaml") -> RuntimeConfig
```

`from_yaml()` 的错误见[异常参考](./exceptions.md)和
[YAML 配置](/configuration/yaml.html)。

## `register_builder`

```python
from bilipy_bot.app import register_builder

register_builder(key: str, builder: Any) -> None
```

builder 接收对应 YAML 顶层值并返回运行时配置对象。重复键覆盖已有 builder；
注册表为进程全局状态。

## 门面中的其他导出

`bilipy_bot.app` 还导出：

- `Event`
- `BaseFilter`、`AndFilter`、`OrFilter`
- `BilipyError` 及公开异常子类

详细定义见 [core API](./core.md) 与 [异常参考](./exceptions.md)。
