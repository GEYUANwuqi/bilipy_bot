---
title: 插件原型基础
---

# 插件原型基础

ButterBot 当前仍然没有正式插件系统。本页描述的是用于验证插件模型的
**provisional 基础 API**，它们允许测试 Source 提供方与 Handler 消费方的解耦，
但不负责发现、导入或信任第三方代码。

## 已提供的基础

| 能力 | API | 语义 |
| --- | --- | --- |
| 逻辑事件源引用 | `SourceRef` | 注册期解析为现有 Source UUID |
| 订阅所有权 | `owner_id`、`SubscriptionHandle` | 精确或按 owner 撤销 |
| owner 回调排空 | `EventBus.drain_owner()` | 等待，超时后取消该 owner 的回调 |
| 配置元数据 | `SourceDefinition` | 保留 `config_key`、`source_name` 和构建结果 |
| 隔离构建器 | `ConfigBuilderRegistry` | 拒绝名称冲突，支持句柄撤销 |
| 注册事务 | `ExtensionRegistrar` | 记录 Source 和订阅，失败时整体清理 |

这些组件保持现有运行模型：

- EventBus 仍使用 Source UUID 作为派发表键；
- 一个匹配的 Handler 仍对应一个独立 `asyncio.Task`；
- `publish()` 的容量和异常语义没有改变；
- Source 仍由 `SourceManager` 启停；
- API 仍由 `ApiRegistry` 按 `(API class, config_key)` 缓存。

## SourceRef

Source 类为具体事件流声明稳定 kind：

```python
class FeedSource(BaseSource):
    source_kind = "example.feed"
    supported_types = FeedType
```

Handler 使用逻辑引用，不导入 `FeedSource`，也不读取随机 UUID：

```python
SourceRef("example.feed", config_key="primary")
```

`source_kind` 表示具体事件能力，不是笼统的平台或配置类型。Bilibili 的内置 kind
分别是：

- `bilibili.dynamic`
- `bilibili.live`
- `bilibili.danmaku`

NapCat 当前使用 `napcat.events`。

`config_key=None` 表示匹配该 kind 的全部实例。调用
`BotApp.get_source(SourceRef(...))` 时，多匹配会抛 `SourceError`，不会偶然选择
第一个实例；`get_sources()` 则显式返回全部匹配项。

## 手工原型

下面的 provider 与 consumer 是两个独立注册单元：

```python
from butterbot.app import (
    BotApp,
    ExtensionRegistrar,
    RuntimeConfig,
    SubscriptionSpec,
)
from butterbot.core.source import SourceRef

app = BotApp(RuntimeConfig())

provider = ExtensionRegistrar(app, "example.provider")
source = provider.add_source(FeedSource, config_key="primary")
provider.commit()


async def on_item(event):
    ...


consumer = ExtensionRegistrar(app, "example.consumer")
consumer.add_subscription(
    SubscriptionSpec(
        source=SourceRef("example.feed", "primary"),
        status=FeedType.ITEM,
        callback=on_item,
    )
)
consumer.commit()
```

consumer 不依赖 `FeedSource` 类，只依赖约定的 source kind、状态和事件数据契约。
关闭 consumer 只撤销它自己的 Handler：

```python
await consumer.aclose()
```

关闭 provider 会停止并移除它创建的 Source。移除 Source 仍会清理该 Source 上的
所有订阅，因此运行期卸载 provider 前必须由未来的插件编排层先处理依赖它的
consumer；当前 registrar 不实现依赖图。

## 注册失败回滚

异步上下文只在代码块正常结束时提交；异常会自动回滚：

```python
async with ExtensionRegistrar(app, "example.extension") as registrar:
    registrar.add_source(FeedSource, config_key="primary")
    registrar.add_subscription(...)
```

显式 `commit()` 后不能继续添加注册项。`aclose()` 和 `rollback()` 均可用于整体
清理且重复调用安全。registrar 不自动启动 Source；装配顺序仍应是：

```text
创建 BotApp
-> 注册全部 Source
-> 注册全部 Handler
-> app.start()
```

应用运行中注册 Source 时，仍需在订阅完成后显式调用
`await app.start_source(source)`。

## 配置构建器原型

`RuntimeConfig.from_yaml()` 会保留 `SourceDefinition`：

```python
definition = config.get_source_definition("primary")
assert definition.source_name == "feed"
assert definition.config is config.get_config("primary")
```

`source_name` 只选择配置 builder，不等同于 `SourceRef.source_kind`。一个
`source_name: bilibili` 配置可供 dynamic、live 和 danmaku 多种 Source 使用。

需要隔离注册表时：

```python
from butterbot.app import ConfigBuilderRegistry, RuntimeConfig

registry = ConfigBuilderRegistry.with_defaults()
registration = registry.register("feed", build_feed_config)
config = RuntimeConfig.from_yaml("config.yaml", builder_registry=registry)
registration.unregister()
```

同名注册默认抛 `ConfigError`。只有明确迁移已有构建器时才使用 `replace=True`；
旧句柄不能撤销后来替换的注册。

## 明确非目标

本阶段没有实现：

- `PluginManifest`、插件基类或统一 PluginContext；
- entry point、目录扫描、启用列表或依赖解析；
- 根据 `source_name` 自动选择 Source factory；
- 运行期延迟绑定新 Source；
- 热重载；
- owner 维度的 API 子集关闭或任意后台任务托管；
- Python 插件沙箱、签名或权限隔离。

因此这些 API 只适合核心仓库内和受控外部包的原型。插件发现层出现之前，不应把
它们声明为稳定插件协议。

## 原型验收边界

当前代码和测试已覆盖：

1. provider 创建 Source，consumer 仅通过 `SourceRef` 订阅；
2. 同 kind 多实例时显式处理歧义或 fan-out；
3. 两个 owner 共享 Source 时，撤销一个不影响另一个；
4. 通配订阅展开到多个状态后仍能用一个句柄完整撤销；
5. 注册中途失败时清理已注册 Source 和 Handler；
6. owner 回调排空超时后只取消该 owner 的任务；
7. 配置 builder 名称冲突和旧句柄误删得到阻止。

下一阶段原型应在测试代码中手工提供 `SourceProvider`/factory，验证至少两种不同
Source 形态后再决定其公开 Protocol；不要先加入自动发现。
