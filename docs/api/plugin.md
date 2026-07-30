---
title: 插件 API
---

# 插件 API

普通业务插件只从 `butterbot.plugin` 导入框架契约：

```python
from butterbot.plugin import (
    Event,
    ButterPlugin,
    PluginRegistrar,
    SourceRef,
    SubscriptionSpec,
)
```

`Event`、过滤器和状态基类由插件门面重新导出，因此 Handler-only 插件不需要知道
`butterbot.core` 的内部布局。只有实现 `BaseSource`、数据模型或新状态类型的事件源
适配作者需要直接导入 core。

## 插件定义

- `ButterPlugin`：本地目录与 distribution 共用的唯一插件基类。
- `PluginDescriptor`：distribution 插件的身份、版本、依赖和 capability。
- `PluginRegistrar`：运行阶段的 owner-aware Source、订阅和关闭回调注册器。
- `ConfigRegistrar`：配置阶段的 builder 和 Source factory 注册器。

本地入口模块必须且只能定义一个具体 `ButterPlugin` 子类。distribution entry point
可以直接指向插件实例、无参类或返回实例的无参 factory，并在子类上提供
`PluginDescriptor`。本地插件的 descriptor 来自 `plugin.toml`，不在 Python
代码中重复声明。

旧名称 `LocalPlugin` 和 `PluginBase` 不再导出。两种来源统一使用
`ButterPlugin`，避免插件作者先判断自己的交付形式再选择基类。

## 包内分层

插件作者始终从 `butterbot.plugin` 门面导入，不依赖内部文件路径。实现按职责分为：

- `contracts/`：`ButterPlugin`、descriptor、Source 路由和订阅声明；
- `discovery/`：entry point 与目录索引、manifest、来源和设置；
- `runtime/`：bootstrap、registrar、manager 和生命周期事务；
- `errors.py`：插件系统共享异常。

`descriptor.py` 只保留 `PluginDescriptor`；标识符校验、hook 基类和路由声明分别位于
独立模块。`discovery/` 与 `runtime/` 通过根门面延迟导出，内部布局仍属于
provisional 实现细节。

## 插件生命周期

`ButterPlugin` 提供四个可选 hook，未覆盖时都是空实现：

```python
class ExamplePlugin(ButterPlugin):
    def register_config(self, registrar: ConfigRegistrar) -> None: ...
    async def register(self, registrar: PluginRegistrar) -> None: ...
    async def on_start(self) -> None: ...
    async def on_stop(self) -> None: ...
```

调用顺序固定为：

1. 按依赖顺序执行同步 `register_config()`；
2. 应用构造后按依赖顺序执行异步 `register()`；
3. 全部 Source 启动成功后按依赖顺序执行 `on_start()`；
4. 停止或关闭时先按依赖逆序执行 `on_stop()`，再撤销 Handler 和 Source。

`register()` 只负责一次性登记，应用重复 start/stop 时不会重复调用；`on_start()` 和
`on_stop()` 则会成对重复。`on_start()` 失败会调用已进入启动阶段插件的
`on_stop()`，再回滚全部插件注册。`on_stop()` 的普通异常会记录并继续清理，取消会在
清理完成后传播。

`registrar.on_close()` 与 `on_stop()` 含义不同：前者登记只在最终关闭或注册回滚时
执行一次的资源释放回调；后者对应每次应用 stop，可在之后再次 start。

## Handler 契约

```python
SourceRef(source_kind: str, config_key: str | None = None)

SubscriptionSpec(
    source: SourceRef,
    status: str | re.Pattern[str] | BaseType,
    callback: Callable[[Event], Coroutine[Any, Any, None]],
    event_filter: BaseFilter | None = None,
    allow_multiple: bool = False,
)
```

`SourceRef` 在注册期由 `SourceCatalog` 解析为 Source UUID。默认要求唯一匹配；
`allow_multiple=True` 才会显式 fan-out。

推荐把 Handler 写成 `ButterPlugin` 的实例方法，再把绑定方法交给
`SubscriptionSpec.callback`。这样 Handler 可以自然复用插件实例状态，代码也不会
散落在入口模块的全局命名空间。

## 控制面

`PluginBootstrap`、`PluginCatalog`、`PluginManager`、来源模型、状态模型和插件异常也
从同一包导出。它们仍是 3.x provisional API，不代表热重载、安全沙箱或运行期安装。
完整的配置、发现和生命周期说明见[实验性插件系统](/extensions/plugins.html)。
