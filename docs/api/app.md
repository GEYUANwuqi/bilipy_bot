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
    *,
    config_path: str | Path | None = None,
    cli_mode: bool = True,
    logging_mode: Literal["managed", "external"] = "managed",
    close_timeout: float = 5.0,
    max_pending_callbacks: int | None = None,
    ctx: AppContext | None = None,
)
```

`config=None` 时调用 `RuntimeConfig.from_yaml(config_path or "config.yaml")`，可能抛
`FileNotFoundError`、`yaml.YAMLError` 或 `ConfigError`。
`config` 和 `config_path` 同时传入时抛 `ValueError`。

配置包含 `sources.<config_key>.kwarg` 时，构造器会用 app 内部的内置 factory 自动
创建并注册 Source。factory registry 不能注入。此阶段不启动 Source。

`cli_mode` 只描述执行宿主，不控制插件。它必须是 `bool`，构造后只能通过只读属性
查询。它只影响 `run(install_signal_handlers=None)` 的默认值：`True` 默认安装
`SIGINT`/`SIGTERM` handler，`False` 默认不安装。`await start()` 和异步上下文
本身都不修改 signal handler。完整用法见
[运行模式与 `run()`](/guide/runtime-modes.md)。

`max_pending_callbacks` 为 `None` 时保持无限并发的兼容行为；设置正整数后，
EventBus 达到该数量的 in-flight Handler task 时会让 `publish()` 等待容量。
注入自定义 `ctx` 时 EventBus 已由该上下文持有，不能同时设置此参数。

`logging_mode="managed"` 会在构造时自动管理 root logger, 所有保持
`propagate=True` 的命名 logger 都使用 ButterBot 的 console/file 格式.
用户不需要导入或调用 `setup_logging()`. 嵌入已管理日志的宿主时,
使用 `logging_mode="external"`; 此模式不修改 root logger, 也不创建日志文件.
并存的 managed 应用共享同配置 handler, 最后一个应用完成
`close()` 后恢复宿主原有日志状态.

### 属性

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `config` | `RuntimeConfig` | 应用运行配置 |
| `plugin_enabled` | `bool` | 最终配置是否启用插件 |
| `cli_mode` | `bool` | 构造期确定的执行宿主模式 |
| `ctx` | `AppContext` | 注入给 Source 的上下文 |
| `bus` | `EventBus` | 事件总线 |
| `api_ctx` | `ApiRegistry` | API 单例容器 |
| `manager` | `SourceManager` | Source 生命周期管理器 |
| `running` | `bool` | manager 是否运行 |
| `closed` | `bool` | manager 是否关闭 |
| `health` | `AppHealth` | 聚合应用、Source 和插件的就绪/健康快照 |

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

::: danger `run()` 默认同步阻塞
`run()` 内部使用 `asyncio.run()`. 默认 `duration=None` 时不会自行返回, 会持续运行到
收到停止信号, 发生 `KeyboardInterrupt`, 抛出未处理异常或进程被外部终止. 调用方
不能期待它在正常服务期间继续执行后续同步语句.
:::

#### `cli_mode` 与信号处理

`install_signal_handlers` 显式值优先于 `cli_mode`：

| `cli_mode` | `install_signal_handlers` | 最终行为 |
| --- | --- | --- |
| `True` | `None` | 安装 `SIGINT`/`SIGTERM` handler |
| `False` | `None` | 不安装 signal handler |
| `True` | `False` | 不安装 signal handler |
| `False` | `True` | 安装 `SIGINT`/`SIGTERM` handler |

handler 安装成功时，两个信号都会唤醒等待逻辑并进入完整 `close()` 路径；`run()`
退出前会移除自己安装的 handler。不支持 `add_signal_handler()` 的平台保留默认行为。
`cli_mode=False` 不影响插件、Source、日志或阻塞语义。

#### `run()` 参数

| 参数 | 默认值 | 语义 |
| --- | --- | --- |
| `duration` | `None` | `None` 持续等待；正数从启动完成后开始计时；`0` 或负数在启动后立即关闭 |
| `install_signal_handlers` | `None` | `None` 使用 `cli_mode`；布尔值显式覆盖；其他类型抛 `TypeError` |
| `health_reporter` | `None` | 同步健康回调；启动后、周期运行时和关闭后报告，通过工作线程执行 |
| `health_interval` | `1.0` | reporter 的周期秒数；提供 reporter 时必须大于 `0` |

`health_reporter=None` 时不创建周期 task，`health_interval` 不参与执行。reporter
异常只记录日志，不中断应用。`duration` 只计算应用启动完成后的等待时间，不包含
配置解析、构造和启动耗时。

`run()` 创建并拥有 event loop，不能在已有 event loop 中调用。`await app.stop()`
不会唤醒 `run()` 的内部等待事件；需要由异步宿主控制退出时，应使用
`async with app` 或手动 `start()`/`close()`。

`start()` 可能抛 `SourceStartError` 或 `PluginRegistrationError`。启动被取消时会
回滚此前已启动的 Source 和插件注册，完成后传播 `CancelledError`。配置启用插件
时，会在 Source 启动前解析并注册插件 Handler，并在全部 Source
启动后按依赖顺序调用插件 `on_start()`。`stop()` 先逆依赖调用插件 `on_stop()`，
再停止 Source；一个或多个 Source 停止失败时抛 `SourceStopError`，但仍会尝试
停止其余 Source。`close()` 同样先执行仍在运行的插件停止回调，再撤销插件
Handler、callback 和插件自身资源，最后按 Source、EventBus、API 顺序释放
其余资源。Source 关闭失败时保留 manager、EventBus 与 API，允许再次调用
`close()`；只有 Source 全部清理成功后才继续关闭下游依赖。`run()` 是拥有事件
循环的同步入口，内部使用 `asyncio.run()`。`health_reporter` 主要供
CLI 定期持久化 `AppHealth`。

`AppHealth.state` 可为 `stopped`、`starting`、`ready`、`degraded` 或
`stopping`。`sources` 包含 Source 类型、逻辑路由和最近成功/异常类型；
`plugins` 仅包含稳定 ID、状态和失败类型，不写入配置值或异常消息。

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
单项。`plugin_enabled` 是环境覆盖后的总开关，`plugin_config` 是插件声明的递归
只读映射，`config_root` 是相对插件路径的解析根。

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

## `SourceCatalog`

`SourceManager.source_catalog` 记录有 `source_kind` 的 Source：

```python
entry = app.manager.source_catalog.entries[0]
assert entry.source_id == source.uuid
assert entry.source_kind == "example.events"
assert entry.config_key == "primary"
```

`SourceRef` 查询通过 catalog 解析。多个 Source 匹配同一逻辑引用时，单项查询抛
`SourceError`；`get_sources()` 可返回全部匹配项。

## 插件集成

`BotApp` 根据最终配置动态导入可选插件运行时，CLI 和直接运行共用该路径。插件作者
只使用[插件 API](./plugin.md)列出的契约；discovery、manager、注册事务和收据是
internal 实现。不使用插件时，直接调用 `BotApp.add_source()` 和
`BotApp.subscribe()`，且框架不会导入任何 `butterbot.plugin` 模块。

`PluginCandidate` 使用 `DistributionPluginOrigin` 或 `DirectoryPluginOrigin`
记录来源；选中后统一成为 `LoadedPlugin` 并进入 `PluginManager`。本地 manifest
转换为 `PluginDescriptor`，本地 entry 模块只需定义唯一 `ButterPlugin` 子类；
loader 自动实例化，不需要 factory。两种来源最终都实例化为 `ButterPlugin` 并进入
同一个 manager。

候选索引总能静态取得 `plugin_name`；本地候选同时暴露目录生成的 `plugin_id`，
distribution 候选则要到被名称选中并加载 descriptor 后才能取得稳定 ID。

`ButterPlugin.settings` 提供当前 owner 隔离的只读私有配置；`resource_root` 对
本地目录插件是 manifest 所在目录，对 distribution 插件为 `None`。
`PluginStatus` 提供稳定 `plugin_id`、与实现类一致的 `plugin_name`、来源类型、来源位置、
可选 fingerprint、`healthy` 和结构化 `failures`，但不保存插件私有配置或异常消息。

## 门面中的其他导出

`butterbot.app` 还导出：

- `Event`
- `SourceDefinition`、`ConfigBuilderRegistry`、`BuilderRegistration`
- `SourceCatalog`、`SourceCatalogEntry`
- `BaseFilter`、`AndFilter`、`OrFilter`
- `ButterError` 及公开异常子类

详细定义见 [core API](./core.md)、[插件 API](./plugin.md)与
[异常参考](./exceptions.md)。
