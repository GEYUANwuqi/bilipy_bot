---
title: 内部设计与约定
---

# 内部设计与约定

## 核心原则

谁创建后台任务，谁保存引用并负责取消与等待。

| 创建者 | 拥有的任务或资源 | 关闭责任 |
| --- | --- | --- |
| Source 实现 | 轮询、监听或 SDK 任务 | `on_stop()` |
| `EventBus` | 每次订阅回调的 task | `EventBus.close()` |
| API 实现 | 连接、监听器、请求 Future | `BaseApi.aclose()` |
| 用户应用 | Source/API 之外自行创建的任务 | 用户自己的 `finally` |

## Source 任务模板

```python
class MySource(BaseSource):
    supported_types = MyType

    def __init__(self) -> None:
        super().__init__()
        self._task: asyncio.Task[None] | None = None

    async def on_start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def on_stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
```

`on_stop()` 可以消费由自己发起的取消；业务代码若在工作过程中收到外部取消，
通常应清理后重新抛出。

## EventBus 的并发语义

同一事件匹配多个 Handler 时，每个 Handler 都作为独立 task 调度，没有顺序
完成保证。异常不会从 `publish()` 传播，而由 done callback 记录日志。

默认 `EventBus()` 不限制 in-flight task，以保持既有行为。对突发流量需要明确
资源上限时，可通过 BotApp 配置：

```python
app = BotApp(
    RuntimeConfig(),
    max_pending_callbacks=100,
)
```

达到容量后，`publish()` 会等待已有 Handler 完成并释放名额，不会静默丢弃事件。
容量限制的是整个 EventBus 的 callback task 数；它不是每个 Handler 的独立队列。
因此 Source 应允许 `publish()` 产生背压，不要把它包装成无界 `create_task()`。

可使用仓库基线脚本比较 unlimited 和有限容量：

```bash
uv run python scripts/benchmark_event_bus.py --events 10000
uv run python scripts/benchmark_event_bus.py --events 10000 --capacity 100
```

该脚本是合成负载，不代表生产吞吐或推荐默认容量。

关闭时：

1. 总线拒绝后续发布；
2. 等待当前所有回调至 `close_timeout`；
3. 取消超时回调；
4. `gather(..., return_exceptions=True)` 等待取消完成。

如果 `close()` 自身在排空期间被取消，总线仍停止接收并尝试取消已纳入关闭的
Handler，然后传播 `CancelledError`。清理被再次取消而未完成时，可以再次调用
`close()`。

## Timeout 与 cancellation

NapCat 请求使用 `asyncio.wait_for()`；超时表现为内置 `TimeoutError`，请求 Future
会在 `finally` 中移除并取消。轮询 Source 捕获单个目标的普通异常后继续下一轮，
但 `CancelledError` 用于退出循环。

## 常见误用

::: danger 丢失任务所有权
不要裸调用 `asyncio.create_task()` 后丢弃返回值。任务可能被回收、异常无人读取，
应用关闭时也无法等待它。
:::

- 在 `on_stop()` 只调用 `task.cancel()` 而不 `await task`；
- Handler 吞掉 `CancelledError` 后继续无限循环；
- 依赖多个 Handler 的完成顺序；
- 启用容量后仍用无界 task 包装 `publish()`，从而绕过背压；
- 使用固定 `sleep()` 代替 Event/Future 做测试同步。

## 相关页面

- [生命周期](./lifecycle.md)
- [异步扩展测试](/extensions/testing.md)
- [异步故障排除](/features/troubleshooting/async-lifecycle.md)
