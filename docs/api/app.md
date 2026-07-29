---
title: 应用 API
---

# 应用 API

## `BotApp`

导入：

```python
from butterbot.app import BotApp
```

签名：

```python
BotApp(
    config: RuntimeConfig | None = None,
    ctx: AppContext | None = None,
    *,
    close_timeout: float = 5.0,
    max_pending_callbacks: int | None = None,
    source_factory_registry: SourceFactoryRegistry | None = None,
)
```

`config=None` 时调用 `RuntimeConfig.from_yaml("config.yaml")`，可能抛
`FileNotFoundError`、`yaml.YAMLError` 或 `ConfigError`。

配置包含 `sources.<config_key>.kwarg` 时，构造器会用内置或传入的
`source_factory_registry` 自动创建并注册 Source。此阶段不启动 Source。

`max_pending_callbacks` 为 `None` 时保持无限并发的兼容行为；设置正整数后，
EventBus 达到该数量的 in-flight Handler task 时会让 `publish()` 等待容量。
注入自定义 `ctx` 时 EventBus 已由该上下文持有，不能同时设置此参数。

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
get_source(source_ref: SourceRef) -> BaseSource | None
get_source(source_cls, config_key=None) -> BaseSourceT | None
get_sources(source_ref: SourceRef) -> tuple[BaseSource, ...]
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
    owner_id: str | None = None,
) -> Callable

add_subscriber(
    source_id: UUID,
    callback: Callable[[Event], Coroutine[Any, Any, None]],
    status: str | re.Pattern[str] | BaseType,
    *,
    event_filter: BaseFilter | None = None,
    owner_id: str | None = None,
) -> SubscriptionHandle

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

`start()` 可能抛 `SourceStartError`。启动被取消时会回滚此前已启动的 Source，
完成后传播 `CancelledError`。`close()` 为终态清理，并按 Source、EventBus、API
顺序尽力释放全部资源；`run()` 是拥有事件循环的同步入口，内部使用
`asyncio.run()`。

## `RuntimeConfig`

导入：

```python
from butterbot.app import RuntimeConfig
```

```python
RuntimeConfig(**configs: Any)
get_config(key: str, default: Any = None) -> Any
RuntimeConfig.from_yaml(
    path: str | Path = "config.yaml",
    *,
    environ: Mapping[str, str] | None = None,
    env_prefix: str = "BUTTERBOT__",
    builder_registry: ConfigBuilderRegistry | None = None,
) -> RuntimeConfig
```

`from_yaml()` 的错误见[异常参考](./exceptions.md)和
[YAML 配置](/configuration/yaml.html)。

`source_definitions` 是只读映射，保留 YAML 中每个命名 Source 的 `config_key`、
`source_name`、`kwarg` 和构建结果；`get_source_definition(config_key)` 可查询
单项。

## `register_builder`

```python
from butterbot.app import register_builder

register_builder(
    key: str,
    builder: Any,
    *,
    replace: bool = False,
) -> BuilderRegistration
```

builder 接收配置值并返回运行时配置对象。新格式由
`sources.<config_key>.source_name` 选择 builder。builder 名称不能直接作为 YAML
顶层键；重复注册默认抛 `ConfigError`，显式 `replace=True` 才会替换。返回句柄的
`unregister()` 只撤销自己仍拥有的注册。

`ConfigBuilderRegistry` 提供隔离注册表；`with_defaults()` 可复制内置构建器，
`RuntimeConfig.from_yaml(builder_registry=...)` 只使用传入实例。

## `SourceFactoryRegistry`

```python
registry = SourceFactoryRegistry.with_defaults()
registry.register(
    source_name: str,
    factory: Callable[..., BaseSource],
    *,
    factory_name: str | None = None,
) -> None
```

注册表把 YAML 的 `source_name + kwarg` 类名解析为 Source 构造工厂。
`with_defaults()` 包含内置 Bilibili 与 NapCat Source。自定义注册表通过
`BotApp(source_factory_registry=registry)` 注入；同名注册抛 `ConfigError`。

## 扩展原型

`ExtensionRegistrar` 和 `SubscriptionSpec` 是 provisional 的手工注册 API，不是
插件加载器。契约、事务语义和非目标见
[插件原型基础](/extensions/prototype-foundations.html)。

## 门面中的其他导出

`butterbot.app` 还导出：

- `Event`
- `SourceDefinition`、`ConfigBuilderRegistry`、`BuilderRegistration`
- `SourceFactoryRegistry`
- `ExtensionRegistrar`、`SubscriptionSpec`
- `BaseFilter`、`AndFilter`、`OrFilter`
- `ButterError` 及公开异常子类

详细定义见 [core API](./core.md) 与 [异常参考](./exceptions.md)。
