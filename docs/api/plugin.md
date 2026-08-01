---
title: 插件 API
---

# 插件 API

`butterbot.plugin` 只导出插件系统自己的契约。普通 Handler 插件通常只需要
`ButterPlugin` 和 `register`；事件类型按需从 `butterbot.core` 导入：

```python
from butterbot.core import Event
from butterbot.plugin import ButterPlugin, register


class HandlerPlugin(ButterPlugin):
    @register("example.events", "example.ready")
    async def handle_ready(self, event: Event) -> None:
        ...
```

`@register(source_kind, status)` 直接声明 Handler 的逻辑订阅。框架会自动：

1. 从插件实例取得 `config_key`；
2. 创建 `SourceRef(source_kind, config_key)`；
3. 用当前绑定方法创建 `SubscriptionSpec`；
4. 通过 owner-aware registrar 注册并记录撤销收据。

因此 Handler 插件不需要导入 `PluginRegistrar`、`SourceRef` 或
`SubscriptionSpec`。

## ButterPlugin 内置上下文

`ButterPlugin` 提供以下实例属性和方法：

```python
self.settings       # 当前插件只读私有配置
self.config         # 声明 config_model 后得到的只读类型化配置
self.context        # 受控的 Source/API 查询和资源作用域
self.context.plugin_name  # manifest/entry point 与实现类共用的名称
self.resource_root  # 本地插件资源根；distribution 插件为 None
self.config_key     # settings["config_key"]；未配置时为 None
self.source_ref("example.events")
```

没有 `config_key` 时，`source_ref()` 只按 `source_kind` 匹配；如果结果唯一，用户
无需写任何配置。同类 Source 有多个实例时，在
`plugins.config.<plugin-id>.config_key` 显式指定一次即可。同一插件的所有
`@register` 声明使用同一个解析结果。需要更特殊的路由策略时，可以覆盖
`source_ref()`。

运行阶段不需要导入 `BotApp`。基类绑定的窄化上下文只提供当前插件需要的查询：

```python
source = self.context.get_source("example.events")
api = self.context.get_api(ExampleApi)  # 默认复用插件级 config_key
```

上下文不会暴露 dispatcher、loader 或其他插件实例。`get_source()` 仍遵守
`SourceRef` 的唯一匹配规则；需要覆盖插件级路由时可显式传入 `config_key`。

## 类型化私有配置

需要强校验时声明 `PluginConfig`。校验发生在应用构造和外部 Source 启动之前：

```python
from butterbot.plugin import ButterPlugin, PluginConfig


class HandlerConfig(PluginConfig):
    config_key: str | None = None
    retry_limit: int = 3


class HandlerPlugin(ButterPlugin[HandlerConfig]):
    config_model = HandlerConfig

    async def on_start(self) -> None:
        assert self.config.retry_limit >= 0
```

`PluginConfig` 默认拒绝未知字段且实例不可修改。未声明 `config_model` 的旧插件继续
使用只读 `settings` mapping，不会被强制迁移。

## register

完整签名：

```python
@register(
    source_kind,
    status,
    event_filter=None,
    allow_multiple=False,
)
```

装饰器只能用于异步实例方法。同一 Handler 可以叠加多个 `@register`；声明按源码
从上到下执行。继承时按基类到子类、类内定义顺序收集；子类同名方法会替换父类
Handler，不加装饰器即可取消继承的订阅。

`event_filter` 接受 core Filter，`allow_multiple=True` 会把声明绑定到所有匹配
Source。默认仍要求 `SourceRef` 唯一匹配。

## Source provider

只有提供配置 builder 或 Source factory 的插件才需要 `configure` 和
`ConfigRegistrar`：

```python
from butterbot.plugin import ButterPlugin, ConfigRegistrar, configure


class SourcePlugin(ButterPlugin):
    @configure
    def configure_source(self, registrar: ConfigRegistrar) -> None:
        registrar.register_builder("example", dict)
        registrar.register_factory(
            "example",
            ExampleSource,
            factory_id="source",
        )
```

`@configure` 方法必须同步；一个插件可以声明多个。普通 Handler 插件不导入这两个
名字。

## 生命周期回调

生命周期由 `PluginManager` 统一编排。插件只需按需覆盖固定回调，不使用装饰器：

```python
class HandlerPlugin(ButterPlugin):
    async def on_start(self) -> None:
        self.context.spawn(self.consume(), name="handler.consume")
        self.context.add_cleanup(self.close_client)

    async def on_stop(self) -> None:
        # 只保留有业务停止顺序要求的逻辑；托管资源由框架兜底。
        await self.flush()
```

全部 Source 启动成功后，`on_start()` 按插件依赖顺序执行；停止 Source 前，
`on_stop()` 按依赖逆序执行。启动失败时，已进入启动阶段的插件也会逆序执行
`on_stop()`，随后撤销本轮注册。回调必须是异步方法；不需要生命周期工作的插件
无需覆盖。

`context.spawn()` 创建的后台任务和 `context.add_cleanup()` 登记的同步或异步回调
属于当前启动周期。框架在 `on_stop()` 之后自动取消并等待任务，再逆序执行清理
回调；`on_start()` 部分初始化后失败时也走同一清理链。后台任务异常会被消费并
写入插件失败记录，不会产生无人读取的 task exception；它不会自动停止整个应用。

生命周期超时由配置统一控制：

```yaml
plugins:
  lifecycle:
    start_timeout: 30
    stop_timeout: 10
    cleanup_timeout: 10
    drain_timeout: 5
```

超时值必须是大于零的有限秒数。回调超时后框架会请求取消并继续处理其他插件；
忽略 `CancelledError` 的插件任务无法被 Python 强制终止，因此会作为 cleaning
失败保留在诊断信息中。

订阅会在 Source 启动前从 `@register` 声明构造，因此不能等到 `on_start()` 再决定
基础路由。长期连接通常仍应实现为 Source，Handler task 由 EventBus 管理。

## 稳定作者 API

- `ButterPlugin`：本地目录和 distribution 共用的唯一插件基类。
- `PluginConfig`：可选的只读私有配置 schema。
- `PluginContext`、`PluginScope`：框架绑定的窄化能力和资源所有权。
- `PluginDescriptor`：插件的稳定 ID、版本、依赖和 capability；本地插件 ID 由
  目录名生成。
- `ConfigRegistrar`、`configure`：Source provider 的配置阶段契约。
- `SourceRef`：覆盖默认路由时使用的逻辑 Source 引用。
- `register`：Handler 声明装饰器。
- `PluginError` 及其公开子类：启动器和调用方可捕获的错误契约。

精确名称以 `butterbot.plugin.__all__` 的 snapshot 测试为准.
`SubscriptionSpec`、registrar 收据、discovery/bootstrap/manager 与运行状态
都是框架 internal 控制面, 不再从 `butterbot.plugin` 根包导出.

本地入口模块必须且只能定义一个具体 `ButterPlugin` 子类。distribution entry point
可以直接指向插件实例、无参类或返回实例的无参 factory，并在子类上提供
`PluginDescriptor`。

插件没有 `@start` 或 `@stop` 装饰器，只有可覆盖的 `on_start()` 和
`on_stop()` 基类回调。应用诊断通过 `BotApp.health` 读取, 不直接暴露
`PluginManager` 或可变的插件运行状态.
