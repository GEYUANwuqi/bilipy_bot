---
title: 应用与上下文
---

# 应用与上下文

## 定义

`BotApp` 是应用入口和资源所有者。它组合：

- `RuntimeConfig`：按键读取的运行配置；
- `AppContext`：注入给 Source 的共享依赖；
- `EventBus`：订阅与异步回调任务；
- `ApiRegistry`：按 API 类型和配置键缓存实例；
- `SourceManager`：Source 注册和生命周期。

## 为什么需要上下文

自定义 Source 不应自己创建第二套事件总线或全局 API 单例。manager 在启动前
调用 `source.bind(ctx)`，Source 再通过 `self.ctx` 访问共享对象：

```python
await self.ctx.bus.publish(self.uuid, event)
api = self.ctx.api_ctx.get(MyApi, self.config_key)
config = self.ctx.config.get_config(self.config_key)
```

Source 未绑定时访问 `self.ctx` 会抛出 `RuntimeError`。因此构造函数只保存静态
参数，不应在 `__init__()` 中读取上下文。

## 注入自定义上下文

测试或高级集成可以注入 `AppContext`：

```python
from butter_bot.app import BotApp, RuntimeConfig
from butter_bot.core.context import AppContext
from butter_bot.core.event import EventBus

config = RuntimeConfig(example={"enabled": True})
ctx = AppContext(config, event_bus=EventBus())
app = BotApp(config, ctx=ctx)
```

传入的 `config` 与 `ctx.config` 应保持一致；构造函数不会替你校验二者是否相同。

## 配置契约

core 层依赖的是 `ConfigProvider` Protocol，而不是具体 `RuntimeConfig`：

```python
from typing import Any


class DictConfig:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)
```

这允许测试或宿主应用提供自己的只读配置对象，同时保持 core 不依赖 YAML。

## 常见误用

- 在 Source 构造函数访问 `self.ctx`；
- 为每个 Source 手工创建 `EventBus`，导致订阅不在应用总线上；
- 调用 `ApiRegistry.clear()` 代替 `aclose_all()`，从而丢弃连接但不释放资源。

## 相关页面

- [配置参考](/configuration/)
- [开发自定义 API](/extensions/api.md)
- [项目架构](/architecture/)
