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
self.resource_root  # 本地插件资源根；distribution 插件为 None
self.config_key     # settings["config_key"]；未配置时为 None
self.source_ref("example.events")
```

没有 `config_key` 时，`source_ref()` 只按 `source_kind` 匹配；如果结果唯一，用户
无需写任何配置。同类 Source 有多个实例时，在
`plugins.config.<plugin-id>.config_key` 显式指定一次即可。同一插件的所有
`@register` 声明使用同一个解析结果。需要更特殊的路由策略时，可以覆盖
`source_ref()`。

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
        ...

    async def on_stop(self) -> None:
        ...
```

全部 Source 启动成功后，`on_start()` 按插件依赖顺序执行；停止 Source 前，
`on_stop()` 按依赖逆序执行。启动失败时，已进入启动阶段的插件也会逆序执行
`on_stop()`，随后撤销本轮注册。回调必须是异步方法；不需要生命周期工作的插件
无需覆盖。依赖 `settings` 或已启动 Source 的实例初始化可以放进 `on_start()`，
对应资源在 `on_stop()` 释放。

订阅会在 Source 启动前从 `@register` 声明构造，因此不能等到 `on_start()` 再决定
基础路由。长期连接通常仍应实现为 Source，Handler task 由 EventBus 管理。

## 身份与低层原语

- `ButterPlugin`：本地目录和 distribution 共用的唯一插件基类。
- `PluginDescriptor`：distribution 插件的身份、版本、依赖和 capability。
- `SourceRef`、`SubscriptionSpec`：应用和手工扩展使用的低层路由声明。
- `PluginRegistrar`、`ExtensionRegistrar`：框架控制面和手工事务扩展使用。

本地入口模块必须且只能定义一个具体 `ButterPlugin` 子类。distribution entry point
可以直接指向插件实例、无参类或返回实例的无参 factory，并在子类上提供
`PluginDescriptor`。

插件没有 `@start` 或 `@stop` 装饰器，只有可覆盖的 `on_start()` 和
`on_stop()` 基类回调。

## 控制面

`PluginBootstrap`、`PluginCatalog`、`PluginManager`、来源模型、状态模型和插件异常
目前仍从同一包导出。它们是 3.x provisional API，不代表热重载、安全沙箱或运行期
安装。
