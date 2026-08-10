---
title: 插件公开 API
---

# 插件 API

`butterbot.plugin` 只导出插件作者契约。插件扩展 Handler 和自身资源，不创建、接管或
配置 Source。

`3.1.0` 起，这些名称属于稳定作者面，并在 `3.x` 内受到 SemVer 兼容承诺保护。

## 最小 Handler

```python
from butterbot.core import Event
from butterbot.plugin import ButterPlugin, register


class HandlerPlugin(ButterPlugin):
    @register("example.events", "example.ready")
    async def handle_ready(self, event: Event) -> None:
        ...
```

`@register` 完整签名：

```python
@register(
    source_kind: str,
    status: object,
    *,
    event_filter: object | None = None,
    allow_multiple: bool = False,
)
```

装饰器只能用于异步实例方法。同一方法可以叠加多个声明；继承时按基类到子类、类内
定义顺序收集，子类同名方法替换父类声明。

框架用 `source_kind` 和插件级 `config_key` 构造 `SourceRef`。默认要求唯一匹配；
`allow_multiple=True` 会订阅全部匹配 Source。Handler 注册发生在 Source 启动前，
缺失或歧义会使应用启动失败。

## `ButterPlugin`

基类提供：

```python
self.settings
self.config
self.context
self.resource_root
self.config_key
self.source_ref("example.events")
```

- `settings`：当前插件隔离的只读配置 mapping。
- `config`：声明 `config_model` 后得到的不可变模型。
- `context`：Source/API 查询与资源作用域。
- `resource_root`：本地 manifest 所在目录；distribution 插件为 `None`。
- `config_key`：`settings["config_key"]`，未设置时为 `None`。
- `source_ref()`：构造逻辑 Source 引用，供高级路由覆盖。

查询已有应用能力：

```python
source = self.context.get_source("example.events")
api = self.context.get_api(ExampleApi)
```

上下文不会暴露可变 registry、Source factory、其他插件实例或配置写回能力。

## `PluginConfig`

```python
from butterbot.plugin import ButterPlugin, PluginConfig


class HandlerConfig(PluginConfig):
    config_key: str | None = None
    retry_limit: int = 3


class HandlerPlugin(ButterPlugin[HandlerConfig]):
    config_model = HandlerConfig
```

模型在应用准备期间校验，默认拒绝未知字段且不可修改。不声明 `config_model` 时继续
使用 `settings`。

## 生命周期

按需覆盖异步回调：

```python
class HandlerPlugin(ButterPlugin):
    async def on_start(self) -> None:
        self.context.spawn(self.consume(), name="handler.consume")
        self.context.add_cleanup(self.close_client)

    async def on_stop(self) -> None:
        await self.flush()
```

全部 Source ready 后按依赖顺序调用 `on_start()`；停止 Source 前按逆依赖顺序调用
`on_stop()`。`context.spawn()` 创建的任务和 `context.add_cleanup()` 登记的同步或
异步回调归当前插件作用域所有，失败回滚和关闭都会兜底清理。

插件没有 `@start`、`@stop` 或 `@configure` 装饰器，也没有 `ConfigRegistrar`。
长期外部事件连接应由应用 Source 实现，不应伪装成插件后台任务。

## `PluginDescriptor`

distribution 插件在类上声明：

```python
from butterbot.plugin import ButterPlugin, PluginDescriptor


class HandlerPlugin(ButterPlugin):
    descriptor = PluginDescriptor(
        plugin_id="example.handler",
        version="1.0.0",
        requires_core=">=3.1,<4",
        requires_plugins=(),
        provides=(),
    )
```

本地目录插件从 `plugin.toml` 构造 descriptor，不在 Python 代码中重复声明。

## 稳定作者 API

`butterbot.plugin.__all__` 包含：

- `ButterPlugin`
- `PluginConfig`
- `PluginContext`、`PluginScope`
- `PluginDescriptor`
- `SourceRef`
- `register`
- `PluginError`、`PluginCompatibilityError`、`PluginDependencyError`、
  `PluginDiscoveryError`、`PluginRegistrationError`

`SubscriptionSpec`、registrar、discovery、manager、运行状态和收据都是框架内部
控制面，不从插件根包导出。插件通过以下 `PluginContext` 方法使用受控运维能力：

- `get_diagnostics()`：读取不含 secret 和异常消息的应用诊断；
- `request_shutdown(ShutdownAction.RESTART, reason=...)`：请求宿主完整关闭后重启；
- `source_control`：启停、删除或按原 YAML 参数重建声明 Source。

框架只提供能力边界，不负责命令鉴权；插件必须在调用变更或退出接口前完成业务
权限检查和高风险操作确认。
