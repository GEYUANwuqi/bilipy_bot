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
EventBus()
add_subscriber(uuid, callback, status, supported_types=None, *, event_filter=None)
subscribe(uuid, status, supported_types=None, *, event_filter=None) -> Callable
remove_subscribers(uuid: UUID) -> int
async publish(uuid: UUID, event: Event) -> None
async close(timeout: float = 5.0) -> None
```

只读属性：

- `closed: bool`
- `pending_callbacks: int`

`publish()` 在总线关闭后记录警告并丢弃事件。Handler 异常记录到日志，不从
`publish()` 抛出。`close()` 幂等，会取消超时 Handler。

`Subscriber` 与 `SubscriberGroup` 从 `butterbot.core.event` 导出，主要用于总线
实现和精细测试；应用订阅优先使用 `BotApp`。

## `BaseSource`

导入：`from butterbot.core.source import BaseSource`

```python
BaseSource(uuid: UUID | None = None, *, config_key: str | None = None)
async start() -> None
async stop() -> None
async on_start() -> None
async on_stop() -> None
bind(ctx: AppContext) -> None
```

子类必须实现 `on_start()`/`on_stop()` 并设置 `supported_types`。属性：
`uuid`、`running`、`is_running`、`config_key`、`ctx`。未绑定访问 `ctx` 抛
`RuntimeError`。

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

`get` 是 `get_api` 别名。`clear()` 只清缓存，不关闭资源。

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
