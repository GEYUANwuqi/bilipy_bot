---
title: BotApp
---

# BotApp

导入：

```python
from butterbot.app import BotApp
```

```python
BotApp(
    config: RuntimeConfig | None = None,
    *,
    config_path: str | Path | None = None,
    cli_mode: bool = True,
    logging_mode: Literal["managed", "external"] = "managed",
    close_timeout: float = 5.0,
    max_pending_callbacks: int | None = None,
    ctx: AppContext | None = None,
)
```

`config=None` 时从 `config_path` 或 `config.yaml` 加载配置。`config` 与
`config_path` 不能同时提供。注入自定义 `ctx` 时不能再设置
`max_pending_callbacks`。

## 属性

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `config` | `RuntimeConfig` | 应用运行配置 |
| `plugin_enabled` | `bool` | 最终配置是否启用插件 |
| `cli_mode` | `bool` | 同步入口的默认信号处理模式 |
| `ctx` | `AppContext` | 注入给 Source 的上下文 |
| `bus` | `EventBus` | 事件总线 |
| `api_ctx` | `ApiRegistry` | API 单例容器 |
| `manager` | `SourceManager` | Source 生命周期管理器 |
| `running` / `closed` | `bool` | 应用运行状态 |
| `health` | `AppHealth` | 应用、Source 与插件的健康快照 |

## Source 管理

```python
add_source(source_cls, *args, **kwargs) -> BaseSourceT
get_source(uuid_or_type_or_ref, config_key=None) -> BaseSource | None
get_sources(source_ref: SourceRef) -> tuple[BaseSource, ...]
async start_source(source_or_uuid) -> BaseSource
async stop_source(source_or_uuid) -> BaseSource
async remove_source(source_id: UUID) -> BaseSource | None
```

`add_source()` 只登记，不自动启动。运行期接入顺序是 add、subscribe、
`start_source()`。详细查询和清理语义见
[SourceManager](/api/source/source-manager.md)。

## API

```python
get_api(api_cls: type[BaseApiT], config_key: str) -> BaseApiT
```

相同 API 类与配置键返回同一实例。容器行为见
[APIContext](/api/api/api-context.md)。

## 订阅

```python
subscribe(
    source_id: UUID,
    status: str | Pattern[str] | BaseType,
    *,
    event_filter: BaseFilter | None = None,
    owner_id: str | None = None,
) -> Callable

add_subscriber(
    source_id: UUID,
    callback: Callable[[Event], Coroutine[Any, Any, None]],
    status: str | Pattern[str] | BaseType,
    *,
    event_filter: BaseFilter | None = None,
    owner_id: str | None = None,
) -> SubscriptionHandle

unsubscribe(source_id: UUID) -> int
```

Source 必须已经登记，回调必须是协程函数。完整规则见 [subscribe](./subscribe.md)。

## 生命周期

```python
async start() -> None
async stop() -> None
async close() -> None
run(
    duration: float | None = None,
    *,
    install_signal_handlers: bool | None = None,
    health_reporter: Callable[[AppHealth], None] | None = None,
    health_interval: float = 1.0,
) -> None
async __aenter__() -> BotApp
async __aexit__(exc_type, exc_val, exc_tb) -> None
```

`run()` 是同步阻塞入口并拥有 event loop，不能从已经运行的 event loop 中调用。
`install_signal_handlers=None` 时使用 `cli_mode` 决定是否安装 `SIGINT` / `SIGTERM`
handler。嵌入式应用优先使用 `async with app`。

关闭顺序为插件、Source、EventBus、API。Source 清理失败时保留下游资源和重试入口；
全部 Source 清理成功后才继续释放 EventBus 与 API。入口选择和信号行为见
[运行模式](/features/runtime-modes.md)，错误类型见 [异常参考](./exceptions.md)。
