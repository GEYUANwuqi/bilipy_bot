---
title: 插件 API
---

# 插件 API

普通业务插件只从 `butterbot.plugin` 导入框架契约：

```python
from butterbot.plugin import (
    Event,
    LocalPlugin,
    PluginRegistrar,
    SourceRef,
    SubscriptionSpec,
)
```

`Event`、过滤器和状态基类由插件门面重新导出，因此 Handler-only 插件不需要知道
`butterbot.core` 的内部布局。只有实现 `BaseSource`、数据模型或新状态类型的事件源
适配作者需要直接导入 core。

## 插件定义

- `LocalPlugin`：本地目录入口模块的自动发现基类。
- `PluginBase`：distribution entry point 插件的可选空 hook 基类。
- `PluginDescriptor`：distribution 插件的身份、版本、依赖和 capability。
- `PluginRegistrar`：运行阶段的 owner-aware Source、订阅和关闭回调注册器。
- `ConfigRegistrar`：配置阶段的 builder 和 Source factory 注册器。

本地入口模块必须且只能定义一个具体 `LocalPlugin` 子类。distribution entry point
可以直接指向插件实例或无参类。

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

## 控制面

`PluginBootstrap`、`PluginCatalog`、`PluginManager`、来源模型、状态模型和插件异常也
从同一包导出。它们仍是 3.x provisional API，不代表热重载、安全沙箱或运行期安装。
完整的配置、发现和生命周期说明见[实验性插件系统](/extensions/plugins.html)。
