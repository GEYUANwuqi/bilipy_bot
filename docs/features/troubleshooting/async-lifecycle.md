---
title: 异步生命周期与资源问题
---

# 异步生命周期与资源问题

## `asyncio.run() cannot be called from a running event loop`

在已有事件循环中调用了 `app.run()` 或嵌套 `asyncio.run()`。

修复：

```python
async with app:
    await do_work()
```

只在最外层脚本使用一次 `asyncio.run(main())`。

## `Task was destroyed but it is pending!`

可能原因：

- Source 创建 task 后未保存；
- 非插件代码创建 task 后没有明确所有者；
- 没有调用 `app.close()`；
- 插件直接调用 `asyncio.create_task()`，绕过了 `PluginScope`。

插件后台任务改用 `self.context.spawn(coro)`，额外资源用
`self.context.add_cleanup(callback)` 登记。Source 自己创建的 task 仍应在
`on_stop()` 中 cancel 并 await。应用入口优先使用 `async with app`。

## 关闭超时

现象：日志显示回调超过 `close_timeout` 后被强制取消。

解决：

- Handler 不要执行无上限等待；
- 网络操作设置 timeout；
- 正确响应 `CancelledError`；
- 根据 `PluginStatus.failures` 区分 starting、stopping、cleaning 和 Handler
  drain；
- 只在确有合理长任务时增大 `BotApp(close_timeout=...)`。

## Source 停止后仍有活动

`stop_source()` 依赖扩展的 `on_stop()`。检查它是否关闭连接、listener、线程并
等待 task。`stop_source()` 保留订阅是预期行为；彻底摘除用 `remove_source()`。

如果 Source 状态为 `stop_failed`，框架仍持有其清理责任；检查第一次停止异常，
修正后再次调用 `stop_source()`、`remove_source()` 或应用 `close()`。不要手工从
manager 字典删除它，否则会丢失最后一个资源句柄。`on_stop()` 必须同时支持完整
启动后的正常关闭和 `on_start()` 部分失败后的回滚。

## NapCat 请求超时

`send_request()` 等待 `receive_timeout`，超时后 pending Future 会清理。检查
WebSocket 是否仍运行、服务器是否回传相同 echo、请求 action 是否受支持。

NapCat 首次连接必须在 `ready_timeout` 内成功，否则 Source 启动直接
抛 `ConnectionError` 并回滚。运行期断线会把 Source `health.state` 置为
`degraded`，重连成功后恢复 `ready` 并更新 `last_success_at`。

## 取消没有被 `except Exception` 捕获

`asyncio.CancelledError` 不应作为普通业务错误吞掉。需要清理时单独捕获：

```python
try:
    await task
except asyncio.CancelledError:
    await cleanup()
    raise
```

由 `on_stop()` 主动取消自己拥有的 task 时，可以在 await 后消费这次预期取消。

## 测试挂起

- 用 `asyncio.Event`/Future 代替固定 sleep；
- 用 `asyncio.wait_for()` 给同步点设置上限；
- 测试结尾 `await bus.close()`；
- 停止 fake Source/API；
- 保持 pytest-asyncio strict 模式。
