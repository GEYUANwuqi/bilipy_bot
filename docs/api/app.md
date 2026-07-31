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

`start()` 可能抛 `SourceStartError` 或 `PluginRegistrationError`。启动被取消时会
回滚此前已启动的 Source 和插件注册，完成后传播 `CancelledError`。存在
PluginManager 时，会在 Source 启动前解析并注册插件 Handler，并在全部 Source
启动后按依赖顺序调用插件 `on_start()`。`stop()` 先逆依赖调用插件 `on_stop()`，
再停止 Source。`close()` 同样先执行仍在运行的插件停止回调，再撤销插件 Handler、
callback、Source 和 registry，最后按 Source、EventBus、API 顺序尽力释放其余
资源。`run()` 是拥有事件循环的同步入口，内部使用 `asyncio.run()`。

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
    owner_id: str | None = None,
) -> FactoryRegistration
```

注册表把 YAML 的 `source_name + kwarg` 类名解析为 Source 构造工厂。
`with_defaults()` 包含内置 Bilibili 与 NapCat Source。自定义注册表通过
`BotApp(source_factory_registry=registry)` 注入；同名注册抛 `ConfigError`。
`factory_name` 是稳定的配置 ID，不要求等于类名。返回收据的 `unregister()` 只在
收据仍拥有该注册时撤销；`resolve()` 返回包含 owner 的 `SourceFactoryEntry`。

## `SourceCatalog`

`SourceManager.source_catalog` 记录有 `source_kind` 的 Source：

```python
entry = app.manager.source_catalog.entries[0]
assert entry.source_id == source.uuid
assert entry.source_kind == "example.events"
assert entry.config_key == "primary"
assert entry.owner_id == "example.plugin"
```

`SourceRef` 查询通过 catalog 解析。插件拥有的重复
`(source_kind, config_key)` 会在应用构造或注册期抛 `SourceError`，避免 Handler
绑定到不确定实现。手工组装的旧式重复 Source 仍保留兼容行为。

## 扩展原型

`SourceRef`、`ExtensionRegistrar`、`SubscriptionSpec`、插件发现、两阶段
bootstrap、依赖状态机和统一回滚都位于独立的 `butterbot.plugin` 命名空间，见
[插件 API](./plugin.md)和
[实验性插件系统](/extensions/plugins.html)。底层手工契约见
[插件原型基础](/extensions/prototype-foundations.html)。

`PluginCandidate` 使用 `DistributionPluginOrigin` 或 `DirectoryPluginOrigin`
记录来源；选中后统一成为 `LoadedPlugin` 并进入 `PluginManager`。本地 manifest
转换为 `PluginDescriptor`，本地 entry 模块只需定义唯一 `ButterPlugin` 子类；
loader 自动实例化，不需要 factory。两种来源最终都实例化为 `ButterPlugin` 并进入
同一个 manager。

`ButterPlugin.settings` 提供当前 owner 隔离的只读私有配置；`resource_root` 对
本地目录插件是 manifest 所在目录，对 distribution 插件为 `None`。
`PluginStatus` 提供来源类型、来源位置和可选 fingerprint，但不保存插件私有配置。

## 门面中的其他导出

`butterbot.app` 还导出：

- `Event`
- `SourceDefinition`、`ConfigBuilderRegistry`、`BuilderRegistration`
- `SourceFactoryRegistry`、`FactoryRegistration`、`SourceFactoryEntry`
- `SourceCatalog`、`SourceCatalogEntry`
- `BaseFilter`、`AndFilter`、`OrFilter`
- `ButterError` 及公开异常子类

详细定义见 [core API](./core.md)、[插件 API](./plugin.md)与
[异常参考](./exceptions.md)。
