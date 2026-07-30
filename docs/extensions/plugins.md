---
title: 实验性插件系统
---

# 实验性插件系统

ButterBot 3.x 提供可信代码、显式启用、仅启动期加载的实验性插件系统。API 位于
`butterbot.app.extensions.experimental`；它仍可能在 3.x 开发版本中发生破坏性
调整。

::: danger 插件拥有当前 Python 进程的完整权限
插件可以访问文件、网络、环境变量和进程内对象。registrar 是生命周期和所有权边界，
不是安全沙箱。只安装并启用可信发布者的插件。
:::

当前不支持运行期安装、单插件卸载、热重载、依赖自动安装、签名验证或插件市场。
插件随应用进程一起加载和关闭。

## 分发与身份

一个插件是独立 Python distribution，并通过固定 entry point group
`butterbot.plugins` 暴露一个插件实例或零参数 factory：

```toml
[project]
name = "butterbot-plugin-example"
version = "1.0.0"
dependencies = ["butterbot-python>=3.1.0.dev2,<4"]

[project.entry-points."butterbot.plugins"]
"example.feed" = "example_plugin:create_plugin"
```

entry point 名必须和 `PluginDescriptor.plugin_id` 完全一致。ID 使用稳定的小写标识，
不要使用可变的类名或展示名称。

```python
from butterbot.app.extensions.experimental import PluginBase, PluginDescriptor


class ExamplePlugin(PluginBase):
    descriptor = PluginDescriptor(
        plugin_id="example.feed",
        version="1.0.0",
        requires_core=">=3.1.0.dev2,<4",
        requires_plugins=(),
        provides=("example.events",),
    )


def create_plugin() -> ExamplePlugin:
    return ExamplePlugin()
```

discovery 只导入 `plugins.enabled` 中列出的 entry point。已安装但未启用的插件不会被
导入。启动前会检查重复 ID、核心版本、必需插件、依赖循环和 capability 冲突，并按
确定的拓扑顺序注册。

## 两阶段注册

配置阶段是同步 hook，只登记 builder 和 Source factory，不能创建任务或连接：

```python
from butterbot.app.extensions.experimental import ConfigRegistrar


class ExamplePlugin(PluginBase):
    # descriptor 同上

    def register_config(self, registrar: ConfigRegistrar) -> None:
        registrar.register_builder("example", dict)
        registrar.register_factory(
            "example",
            FeedSource,
            factory_id="source",
        )
```

`factory_id="source"` 是 YAML 协议。它不依赖 `FeedSource` 的 Python 类名，因此类
重命名不会破坏用户配置。

运行阶段是异步 hook。Source provider 可创建 Source；Handler-only 插件只通过
`SourceRef` 依赖逻辑事件能力，不需要导入 provider 的 Source 类：

```python
from butterbot.app.extensions.experimental import (
    PluginRegistrar,
    SubscriptionSpec,
)
from butterbot.core.source import SourceRef


async def on_item(event) -> None:
    ...


class HandlerPlugin(PluginBase):
    descriptor = PluginDescriptor(
        plugin_id="example.handler",
        version="1.0.0",
        requires_core=">=3.1.0.dev2,<4",
        requires_plugins=("example.feed",),
        provides=("example.handler",),
    )

    async def register(self, registrar: PluginRegistrar) -> None:
        registrar.add_subscription(
            SubscriptionSpec(
                source=SourceRef("example.events", "primary"),
                status="example.item",
                callback=on_item,
            )
        )
        registrar.on_close(close_plugin_resource)
```

`PluginManager` 注入 owner ID。插件不能代替其他插件登记 Source 或 Handler。
L1 插件不得在 registrar 之外创建后台 task；长期任务应由 Source 的
`on_start()`/`on_stop()` 管理，Handler task 由 EventBus 管理。

## 配置与应用 factory

只启用明确需要的插件：

```yaml
plugins:
  enabled:
    - example.feed
    - example.handler

sources:
  primary:
    source_name: example
    kwarg:
      source: {}
```

`plugins` 是 bootstrap 保留段，不会进入 `RuntimeConfig.get_config()`。可以使用
`BUTTERBOT__PLUGINS__ENABLED='[example.feed, example.handler]'` 覆盖启用列表。

插件模式需要一个同步应用 factory，让 bootstrap 在解析配置前注入插件 builder，
并在构造 Source 前注入插件 factory：

```python
from butterbot.app import BotApp, RuntimeConfig, SourceFactoryRegistry


def create_app(
    *,
    config: RuntimeConfig,
    source_factory_registry: SourceFactoryRegistry,
) -> BotApp:
    return BotApp(
        config=config,
        source_factory_registry=source_factory_registry,
    )
```

先校验再运行：

```bash
butterbot check mybot.app:create_app
butterbot run mybot.app:create_app
```

`check` 执行与 `run` 相同的发现、配置解析、应用构造和插件注册，但不会启动外部
Source。省略 check 的 entry point 时使用默认 `BotApp` factory。

代码内也可显式拥有 bootstrap：

```python
from butterbot.app.extensions.experimental import PluginBootstrap

bootstrap = PluginBootstrap("config.yaml")
app = bootstrap.build(create_app)
manager = bootstrap.manager
assert manager is not None
```

不要在插件模式中先构造全局 `BotApp` 对象；那会早于插件 builder/factory 注册。
没有启用插件时，原有 `BotApp()`、手工装配和零参数应用 factory 保持可用。

## 生命周期、回滚与诊断

顺序固定为：

```text
显式发现
-> descriptor/依赖校验
-> register_config（依赖顺序）
-> 解析 RuntimeConfig
-> 构造全部配置 Source
-> register（依赖顺序）
-> 启动 Source
-> 运行
-> 插件逆依赖顺序关闭
-> SourceManager / EventBus / ApiRegistry 关闭
```

builder、factory、Source、Handler 和 close callback 都有 owner 与撤销收据。配置、
注册或 Source 启动出现普通异常或取消时，bootstrap 会逆序撤销本轮副作用。
`SourceRef` 缺失、重复或歧义在 Source 启动前报告。

`PluginBootstrap.manager.statuses` 返回不含配置值和 secret 的诊断快照。状态包括
`validated`、`configuring`、`configured`、`registering`、`registered`、
`started`、`failed`、`blocked` 和 `closed`。注册异常还提供
`PluginRegistrationError.plugin_id`、`phase` 和 `cause`。

## 发布前验证

插件至少应在独立 wheel 中验证：

- entry point 能从 clean venv 发现；
- distribution 只导入公开或 experimental 接口；
- provider/consumer 不通过实现类互相耦合；
- import、register 和 Source start 失败不留下注册项或 task；
- 重复关闭幂等。

核心仓库的 `scripts/smoke_plugins.py` 使用 Source-only、Handler-only 和 Combined
三个独立 distribution，在 Python 3.12、3.13 和 3.14 CI 上执行这一契约。

手工扩展的底层原语仍见[插件原型基础](./prototype-foundations.md)。
