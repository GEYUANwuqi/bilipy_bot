---
title: 运行模式
---

# 运行模式与 `run()`

## 先看结论

`cli_mode` 只决定 `BotApp.run()` 的默认信号处理策略. 它不决定插件是否启用,
不选择日志模式, 不改变 Source 装配, 也不会让 `run()` 从阻塞调用变成非阻塞调用.

| 行为 | `cli_mode=True` | `cli_mode=False` |
| --- | --- | --- |
| `run()` 默认安装 `SIGINT`/`SIGTERM` handler | 是 | 否 |
| `run()` 是否同步阻塞 | 是 | 是 |
| `run()` 是否创建并拥有 event loop | 是 | 是 |
| `await start()` 是否安装 signal handler | 否 | 否 |
| `async with app` 是否安装 signal handler | 否 | 否 |
| 是否启用插件 | 只取决于 `config.plugin_enabled` | 只取决于 `config.plugin_enabled` |
| 是否修改宿主日志 | 只取决于 `logging_mode` | 只取决于 `logging_mode` |

因此:

- 独立脚本或 CLI 进程通常使用 `cli_mode=True`;
- 嵌入 ASGI, Jupyter 或已有 asyncio 应用时使用 `cli_mode=False`, 并通过
  `async with app` 或 `await start()`/`await close()` 管理生命周期;
- `cli_mode=False` 不等于关闭插件;
- `cli_mode=False` 也不等于 `run()` 会立即返回.

## `cli_mode` 的构造期语义

`cli_mode` 是 `BotApp` 的构造参数, 默认值为 `True`:

```python
BotApp(
    config: RuntimeConfig | None = None,
    *,
    cli_mode: bool = True,
    ...,
)
```

它必须是 `bool`; 其他类型会抛出 `TypeError`. 构造后可以通过只读属性
`app.cli_mode` 查询, 不能在运行期切换.

ButterBot CLI 会先解析 `RuntimeConfig`, 再以 `cli_mode=True` 调用应用工厂:

```python
def app(*, config: RuntimeConfig, cli_mode: bool = True) -> BotApp:
    return BotApp(config=config, cli_mode=cli_mode)
```

直接构造 `BotApp()` 时默认同样是 `True`. 如果应用由其他框架托管, 应显式传入
`False`:

```python
app = BotApp(
    config=config,
    cli_mode=False,
    logging_mode="external",
)
```

`logging_mode="external"` 不是 `cli_mode=False` 的隐含行为. 两个参数需要分别设置:
前者保留宿主日志配置, 后者保留宿主信号处理权.

## `run()` 完整签名

```python
run(
    duration: float | None = None,
    *,
    install_signal_handlers: bool | None = None,
    health_reporter: Callable[[AppHealth], None] | None = None,
    health_interval: float = 1.0,
) -> None
```

`run()` 是同步阻塞入口. 它内部调用 `asyncio.run()`, 创建并拥有一个新的 event
loop, 启动应用, 等待退出条件, 最后执行完整的 `close()` 路径. 不能从一个正在运行
的 event loop 中调用它.

### `duration`

类型为 `float | None`, 默认值为 `None`.

- `None`: 不设置运行时限, 持续等待停止信号或中断;
- 正数: 从应用完成启动并进入等待阶段开始计时, 到期后正常关闭并返回;
- `0` 或负数: 当前实现会在启动完成后立即进入正常关闭路径.

`duration` 不是整个进程的墙钟超时. 配置解析, 应用构造和 Source/插件启动耗时不
计入这段等待时间. 生产服务通常保留 `None`; 限时任务和测试可以传正数:

```python
app.run(duration=30.0)
```

### `install_signal_handlers`

类型为 `bool | None`, 默认值为 `None`. 非布尔且非 `None` 的值会抛出
`TypeError`.

它对 `cli_mode` 的覆盖关系如下:

| `cli_mode` | `install_signal_handlers` | 最终行为 |
| --- | --- | --- |
| `True` | `None` | 安装 `SIGINT`/`SIGTERM` handler |
| `False` | `None` | 不安装 signal handler |
| `True` | `False` | 显式不安装 signal handler |
| `False` | `True` | 显式安装 `SIGINT`/`SIGTERM` handler |

安装成功后, `SIGINT` 或 `SIGTERM` 会唤醒 `run()` 的等待逻辑, 让应用经过
`close()` 正常退出. `run()` 返回前会移除自己安装的 handler. 如果当前平台或
event loop 不支持 `add_signal_handler()`, ButterBot 记录 debug 日志并保留平台
默认行为.

当 `cli_mode=False` 且没有显式开启信号处理时, `run(duration=None)` 没有由
ButterBot 管理的停止信号. `SIGTERM` 可能直接采用宿主或操作系统的默认行为, 无法
保证进入 `close()`. 嵌入式应用应让宿主等待自己的 shutdown event, 然后调用
`await app.close()`.

### `health_reporter`

类型为 `Callable[[AppHealth], None] | None`, 默认值为 `None`.

传入同步回调后, `run()` 会:

1. 在应用启动完成后立即报告一次;
2. 运行期间每隔 `health_interval` 报告一次;
3. 退出和清理完成后再报告一次最终快照.

回调通过工作线程执行, 不阻塞 event loop. 回调异常只写入日志, 不终止应用.
这个参数主要供 CLI 持久化健康摘要; 普通应用不需要设置. `None` 时不会创建周期
健康报告 task.

```python
def report(health: AppHealth) -> None:
    print(health.state)


app.run(health_reporter=report, health_interval=2.0)
```

### `health_interval`

类型为 `float`, 默认值为 `1.0`, 单位是秒. 只有提供 `health_reporter` 时才参与
执行. 此时它必须大于 `0`, 否则抛出 `ValueError`. 没有提供 reporter 时不会创建
周期 task, `health_interval` 也不会影响运行.

## 退出与异常语义

以下情况会结束 `run()`:

- `duration` 到期;
- ButterBot 安装的 `SIGINT`/`SIGTERM` handler 被触发;
- 平台默认行为产生 `KeyboardInterrupt`;
- 启动, 运行或关闭阶段抛出未处理异常;
- 进程被无法处理的外部机制终止.

时限到期和 ButterBot 管理的停止信号会走正常异步上下文退出路径. `run()` 捕获
`KeyboardInterrupt` 并记录中断日志. 其他未处理异常会在完成可执行的清理后继续
向调用方传播.

`await app.stop()` 不会唤醒 `run()` 内部的等待事件. `stop()` 的含义是停止插件
和 Source 但保留可再次启动的运行时注册, 它不是结束 `run()` 的跨任务控制接口.
需要由宿主控制退出时, 不要把 `run()` 放进线程后再调用 `stop()`; 应直接使用异步
生命周期 API.

## 推荐用法

### CLI 或独立服务进程

```python
app = BotApp(config=config, cli_mode=True)
app.run()
```

默认接管 `SIGINT` 和 `SIGTERM`, 适合终端, 容器和 systemd.

### 嵌入已有 asyncio 应用

```python
app = BotApp(
    config=config,
    cli_mode=False,
    logging_mode="external",
)

async with app:
    await host_shutdown_event.wait()
```

宿主保留 event loop, signal handler 和日志配置的所有权. `async with` 只负责
ButterBot 的启动与关闭.

### 同步宿主但由调用方处理信号

```python
app = BotApp(config=config, cli_mode=False)
app.run(duration=60.0, install_signal_handlers=False)
```

这种模式仍然同步阻塞, 只是 ButterBot 不修改 signal handler. 如果没有
`duration`, 调用方必须确保平台默认中断能够结束进程, 或改用异步生命周期 API.

## 相关页面

- [生命周期](/architecture/lifecycle.md)
- [CLI](./cli.md)
- [BotApp API](/api/bot-app.md)
- [异步生命周期故障排除](./troubleshooting/async-lifecycle.md)
