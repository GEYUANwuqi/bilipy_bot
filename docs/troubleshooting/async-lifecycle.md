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
- `on_stop()` 只 cancel 没有 await；
- 没有调用 `app.close()`；
- 用户自己创建的 task 不属于 EventBus，未在 finally 清理。

排查任务创建点 `asyncio.create_task()`，逐一确认所有权。优先使用
`async with app`。

## 关闭超时

现象：日志显示回调超过 `close_timeout` 后被强制取消。

解决：

- Handler 不要执行无上限等待；
- 网络操作设置 timeout；
- 正确响应 `CancelledError`；
- 只在确有合理长任务时增大 `BotApp(close_timeout=...)`。

## Source 停止后仍有活动

`stop_source()` 依赖扩展的 `on_stop()`。检查它是否关闭连接、listener、线程并
等待 task。`stop_source()` 保留订阅是预期行为；彻底摘除用 `remove_source()`。

## NapCat 请求超时

`send_request()` 等待 `receive_timeout`，超时后 pending Future 会清理。检查
WebSocket 是否仍运行、服务器是否回传相同 echo、请求 action 是否受支持。

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
