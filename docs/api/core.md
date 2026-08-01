---
title: 核心扩展 API
---

# 核心扩展 API

## `Event[T]`

导入：`from butterbot.core.event import Event`

```python
@dataclass
class Event(Generic[BaseDataT]):
    data: BaseDataT
    status: BaseType
    id: str = ...
```

`id` 默认由 `uuid4()` 生成。构造器不验证 data 与 status 的语义对应。

## `EventBus`

导入：`from butterbot.core.event import EventBus`

```python
EventBus(*, max_pending_callbacks: int | None = None)
add_subscriber(
    uuid, callback, status, supported_types=None, *,
    event_filter=None, owner_id=None
) -> SubscriptionHandle
subscribe(
    uuid, status, supported_types=None, *,
    event_filter=None, owner_id=None
) -> Callable
remove_subscribers(uuid: UUID) -> int
remove_subscription(handle: SubscriptionHandle) -> bool
remove_subscribers_by_owner(owner_id: str) -> int
async drain_owner(owner_id: str, timeout: float = 5.0) -> int
async publish(uuid: UUID, event: Event) -> None
async close(timeout: float = 5.0) -> None
```

只读属性：

- `closed: bool`
- `pending_callbacks: int`
- `max_pending_callbacks: int | None`

`pending_callbacks_for(owner_id)` 返回指定 owner 的运行中回调数量。退订只阻止后续
派发；`drain_owner()` 等待已经开始的回调，并在超时后只取消该 owner 的任务。

`publish()` 在总线关闭后记录警告并丢弃事件。Handler 异常记录到日志，不从
`publish()` 抛出。配置容量后，`publish()` 可能等待可用名额；默认 `None` 保持
无限制行为。`close()` 幂等，会取消超时 Handler；关闭过程自身被取消时仍会尝试
回收已纳入关闭的回调，未完成清理时可再次调用。

`Subscriber` 与 `SubscriberGroup` 从 `butterbot.core.event` 导出，主要用于总线
实现和精细测试；应用订阅优先使用 `BotApp`。

## `BaseSource`

导入：

```python
from butterbot.core.source import BaseSource, SourceHealthState, SourceState
```

```python
BaseSource(uuid: UUID | None = None, *, config_key: str | None = None)
async start() -> None
async stop() -> None
async on_start() -> None
async on_stop() -> None
bind(ctx: AppContext) -> None
```

子类必须实现 `on_start()`/`on_stop()` 并设置 `supported_types`。属性：
`uuid`、`running`、`is_running`、`state`、`cleanup_required`、`health`、`source_kind`、
`config_key`、`ctx`。未绑定访问 `ctx` 抛 `RuntimeError`。参与逻辑路由的 Source
还需声明非空 `source_kind`。

`state` 是 `SourceState`，可能为 `stopped`、`starting`、`running`、`stopping`
或 `stop_failed`。`on_start()` 失败时框架会调用 `on_stop()` 回滚部分资源，再传播
原始启动异常，因此 `on_stop()` 必须容忍部分初始化。`on_stop()` 失败或被取消时，
`cleanup_required` 保持为 true，下一次 `stop()` 会重试清理；清理完成前再次
`start()` 抛 `LifecycleError`。同一 Source 的 start/stop 调用由生命周期锁串行化。

`health` 是只读 `SourceHealth`快照，状态为 `stopped`、`starting`、
`ready`、`degraded` 或 `stopping`，并提供 `last_success_at`、
`last_error_at`、`last_error_type` 和 `last_error_message`。普通 Source 在
`on_start()` 返回后自动进入 ready；长连接 Source 可在断线和恢复时
更新该快照。

## `BaseApi`

导入：`from butterbot.core.api import BaseApi`

```python
class BaseApi(ABC):
    @classmethod
    def create(cls, ctx: ApiRegistry, config_key: str) -> Self: ...

    async def aclose(self) -> None: ...
```

`__init__` 和 `create` 是抽象方法。`aclose()` 默认无操作；有资源的 API 应覆写
并保证幂等。

## Context

### `ConfigProvider`

Protocol：

```python
get_config(key: str, default: Any = None) -> Any
```

### `AppContext`

```python
AppContext(
    config: ConfigProvider,
    event_bus: EventBus | None = None,
    api_ctx: ApiRegistry | None = None,
)
```

只读属性：`config`、`bus`、`api_ctx`。

### `ApiRegistry`

```python
ApiRegistry(config: ConfigProvider)
get_api(cls, config_key: str) -> BaseApiT
get(cls, config_key: str) -> BaseApiT
require_config(config_key: str) -> Any
async aclose_all() -> None
clear() -> None
```

`get` 是 `get_api` 别名。`clear()` 只清缓存，不关闭资源。`aclose_all()` 遇到
单个 API 的普通异常或取消时继续关闭其余实例，并在清理完成后传播观察到的
`CancelledError`。

## Type

`BaseType(str, Enum)`：

```python
scope: str
state: str
matches(rule: str | re.Pattern[str] | BaseType) -> bool
matching_statuses(rule) -> list[BaseType]
```

字符串按正则 `fullmatch`。`matching_statuses()` 排除 state 为 `all` 的成员。

## Filter

```python
class BaseFilter(ABC):
    filters: Any
    def check(event: Event) -> bool: ...
    def __and__(other) -> BaseFilter: ...
    def __or__(other) -> BaseFilter: ...
```

`AndFilter(*filters)` 与 `OrFilter(*filters)` 按顺序短路。

## Data

`butterbot.core.data` 公开：

- `BaseDataMixin`
- `BaseDataModel`
- `AutoDispatchList`
- `BaseDataT`

`BaseDataModel` 的高价值构造方法：

```python
from_raw(raw: dict) -> Self
from_dict(raw: dict) -> Self
from_type(data: dict, type_value: str, raw: bool = True) -> Self
```

`from_raw()` 在基类只是扩展占位；具体模型需要实现时应覆写。

## 类型变量

core 导出 `BaseApiT`、`BaseSourceT`、`BaseDataT`、`BaseTypeT`，用于扩展签名。
它们是 `TypeVar`，不是运行时注册器。
