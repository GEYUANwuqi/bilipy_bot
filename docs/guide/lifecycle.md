---
title: 生命周期
---

# 生命周期

## 本页目标

选择正确的 asyncio 入口，并理解启动、停止、关闭、取消与超时行为。

## 三种运行方式

### 已有异步入口：优先使用 `async with`

```python
import asyncio

from butterbot.app import BotApp, RuntimeConfig


async def main() -> None:
    app = BotApp(RuntimeConfig())
    async with app:
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
```

`__aenter__()` 调用 `start()`，`__aexit__()` 无论代码块是否抛异常都会调用
`close()`，原异常不会被上下文管理器吞掉。

### 简单脚本：`app.run()`

```python
from butterbot.app import BotApp

app = BotApp()  # 默认读取当前目录的 config.yaml
app.run()
```

`run()` 自己调用 `asyncio.run()`，适合没有现成事件循环的顶层脚本。不要在
Jupyter、ASGI 服务或其他已运行的协程中调用它。

部署入口也可以使用 [ButterBot 命令行](./cli.md) 加载模块中的 `BotApp` 对象。
CLI 最终仍调用同一个 `BotApp.run()`，不会改变关闭顺序。

::: warning CLI 入口不能在导入时运行
单 Bot 项目推荐由 CLI 管理进程。供 CLI 导入的 `app.py` 只创建 `app`、添加
Source 并注册 Handler，不要在模块顶层调用 `app.run()`。
:::

如果同一个文件还需要支持 `uv run app.py`，使用主模块保护：

```python
from butterbot.app import BotApp

app = BotApp()


if __name__ == "__main__":
    app.run()
```

选择规则：

| 场景 | 推荐入口 |
| --- | --- |
| 单 Bot 项目、需要后台管理 | `butterbot run app:app --background` |
| 直接执行 Python 文件 | `if __name__ == "__main__": app.run()` |
| 同步宿主且没有现有事件循环 | 由宿主调用 `app.run()` |
| ASGI/Jupyter/现有 asyncio 应用 | `async with app` 或手动 `start()`/`close()` |

CLI 的 `stop` 是操作系统级进程暂停，不调用 `BotApp.stop()`。两者的资源和恢复语义
不同，详见[命令行的暂停与恢复](./cli.md#暂停与恢复)。

传入 `duration` 可以在指定秒数后正常关闭：

```python
app.run(duration=30)
```

### 手动控制

```python
app = BotApp(RuntimeConfig())
try:
    await app.start()
    await do_work()
finally:
    await app.close()
```

只有需要把生命周期拆开时使用。`stop()` 不是 `close()` 的替代品。

## 启动语义

`BotApp.start()` 委托给 `SourceManager.start()`，按注册顺序绑定上下文并启动
Source。任一 Source 启动失败时：

- 失败源的 `running` 会回滚为 `False`；
- 已成功启动的 Source 会被停止；
- 抛出 `SourceStartError`，其 `failures` 保存原始异常；
- manager 不进入运行状态。

启动协程被取消时也会停止此前已成功启动的 Source，再传播
`asyncio.CancelledError`，不会留下半启动 manager。

## 停止与关闭的区别

`await app.stop()` 只停止已注册 Source，保留 Source、订阅、EventBus 与 API
缓存，可再次启动。

`await app.close()` 是终态操作，顺序固定：

1. `SourceManager.close()`：停止 Source，不再产生新事件；
2. `EventBus.close()`：等待正在执行的 Handler；
3. `ApiRegistry.aclose_all()`：关闭 API 连接和任务。

关闭后不要再次启动或添加 Source。

## 回调超时

`BotApp(close_timeout=5.0)` 的默认关闭等待为 5 秒。超过该时间仍未完成的
Handler task 会被取消并等待到真正结束：

```python
app = BotApp(RuntimeConfig(), close_timeout=1.0)
```

Handler 若捕获 `asyncio.CancelledError`，完成必要清理后应重新抛出，不要无限
忽略取消，否则会阻塞应用关闭。

## 取消传播

`BaseSource.start()` 捕获 `BaseException` 来保证启动取消时回滚状态，然后原样
传播。`SourceManager.stop()` 会继续清理其余 Source，最后重新抛出观察到的
`CancelledError`。动态移除 Source 时，即使停止被取消，也会完成退订和摘除。
`BotApp.close()` 使用嵌套 `finally`，manager 或 EventBus 清理被取消时仍会继续
关闭后续资源；`ApiRegistry` 也会继续处理其余 API，最后再传播取消。

## 常见误用

::: danger 不要这样启动事件循环
不要调用 `asyncio.get_event_loop().run_until_complete(...)`，也不要在协程里嵌套
`asyncio.run()`。项目支持的用户入口是顶层 `asyncio.run(main())`。
:::

::: warning 不要只调用 `stop()`
只调用 `stop()` 可能留下 EventBus 回调和 API 连接。应用退出路径应调用
`close()`，或使用 `async with app`。
:::

## 下一步

- [并发与任务所有权](/concepts/concurrency.md)
- [错误传播](/concepts/errors.md)
- [生命周期故障排除](/troubleshooting/async-lifecycle.md)
