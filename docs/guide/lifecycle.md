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

`cli_mode`、`duration`、信号覆盖关系和健康报告参数的完整说明见
[运行模式与 `run()`](./runtime-modes.md)。特别注意，`cli_mode=False` 只关闭
`run()` 的默认 signal handler，不会关闭插件，也不会让 `run()` 变成非阻塞调用。

::: danger 默认调用会持续阻塞
`app.run()` 是同步阻塞入口. 默认 `duration=None`, 不会自行返回. 它会一直运行到
收到 `SIGINT`, `SIGTERM`, `KeyboardInterrupt`, 遇到未处理异常或进程被外部终止.
后续 Python 语句在正常服务期间不会执行.
:::

部署入口也可以使用 [ButterBot 命令行](./cli.md). CLI 通过同步工厂构造 `BotApp` 后仍
调用同一个 `BotApp.run()`，不会改变关闭顺序。

::: warning CLI 入口不能在导入时运行
单 Bot 项目推荐由 CLI 管理进程。供 CLI 导入的 `app.py` 只提供应用入口，不要在
模块顶层调用 `app.run()`。
:::

`butterbot init` 默认生成具名同步工厂入口. CLI 入口只推荐这一种官方协议.
见[命令行](./cli.md).

如果选择直接执行 Python 文件，而不是把它作为 CLI 入口，使用主模块保护：

```python
from butterbot.app import BotApp

app = BotApp()


if __name__ == "__main__":
    app.run()
```

选择规则：

| 场景 | 推荐入口 |
| --- | --- |
| 单 Bot 项目、需要后台管理 | `butterbot run --background` |
| 直接执行 Python 文件 | `if __name__ == "__main__": app.run()` |
| 同步宿主且没有现有事件循环 | 由宿主调用 `app.run()` |
| ASGI/Jupyter/现有 asyncio 应用 | `async with app` 或手动 `start()`/`close()` |

CLI 的 `stop` 向受管进程发送 `SIGTERM`，由 `BotApp.run()` 进入 `close()` 清理；
它不是 `BotApp.stop()` 的远程调用。详见[命令行的状态与优雅停止](./cli.md#状态与优雅停止)。

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

`BotApp.start()` 先完成插件 Handler 注册，再委托给 `SourceManager.start()` 按
注册顺序绑定上下文并启动 Source。全部 Source 就绪后，插件的 `on_start()` 按依赖
顺序执行。任一 Source 启动失败时：

- 失败源的 `running` 会回滚为 `False`；
- 框架调用失败源的 `on_stop()` 回滚部分初始化，因此该方法必须容忍未完整启动；
- 已成功启动的 Source 会被停止；
- 抛出 `SourceStartError`，其 `failures` 保存原始异常；
- 回滚停止失败的 Source 会保留 `cleanup_required`，manager 不丢失其句柄。

启动协程被取消时也会停止此前已成功启动的 Source，再传播
`asyncio.CancelledError`，不会留下半启动 manager。

插件 `on_start()` 发生异常或取消时，当前插件和此前已启动插件会先按依赖逆序执行
`on_stop()`，再关闭各自 `PluginScope` 中的后台任务和清理回调，然后撤销 Handler、
插件自身资源注册。普通异常包装为 `PluginRegistrationError`；取消在清理
完成后原样传播。

## 停止与关闭的区别

`await app.stop()` 先按依赖逆序执行插件 `on_stop()`，再停止已注册 Source，但保留
Source、插件 Handler 注册、EventBus 与 API 缓存，因此可以再次启动。下一次
`start()` 不会重复注册 Handler，但会在 Source 重新就绪后再次执行 `on_start()`。
停止会尝试全部 Source；普通失败聚合为 `SourceStopError`，取消在其余 Source
处理后传播。失败 Source 进入 `stop_failed`，再次 `stop()` 会重试。

`await app.close()` 是终态操作，顺序固定：

1. `PluginManager.aclose()`：先逆依赖执行仍在运行的插件 `on_stop()`，再撤销插件
   托管任务、Handler 和 close callback；
2. `SourceManager.close()`：停止其余 Source，不再产生新事件；
3. `EventBus.close()`：等待正在执行的 Handler；
4. `ApiRegistry.aclose_all()`：关闭 API 连接和任务。

关闭后不要再次启动或添加 Source。

如果 Source 停止失败，`SourceManager.close()` 不会清空注册或进入 closed；
`BotApp.close()` 也不会继续关闭 EventBus/API。manager 会进入只允许清理的
closing 阶段，禁止添加和启动新 Source。修正瞬时故障后再次调用 `close()` 即可
重试。这样 Source 不会失去最后一个资源句柄，也不会在 API 已关闭后才被迫清理。

## 回调超时

插件生命周期分别受 `plugins.lifecycle.start_timeout`、`stop_timeout`、
`cleanup_timeout` 和 `drain_timeout` 限制。一个插件超时不会跳过其余插件的逆序
停止和清理；失败会进入 `PluginStatus.failures`。存在 stopping 或 cleaning
失败时，该插件状态为 `failed`，同一个 manager 不允许再次启动。

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
`CancelledError`。插件 `on_stop()` 被取消时，`PluginManager` 也会继续调用其余
插件的停止回调。动态移除 Source 时，停止被取消会保留订阅与注册，下一次调用
继续清理。`BotApp.close()` 只有在 Source 全部停止后才关闭 EventBus 和 API；
EventBus 关闭被取消时仍会尝试关闭 API，最后再传播取消。

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
