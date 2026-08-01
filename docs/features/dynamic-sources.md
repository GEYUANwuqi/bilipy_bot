---
title: 运行期管理事件源
---

# 运行期管理事件源

## 本页目标

在 `BotApp` 已运行时接入、暂停、恢复或移除 Source，并避免启动前丢事件。

## 运行中接入

顺序必须是“注册 → 订阅 → 启动”：

```python
source = app.add_source(MySource)


@app.subscribe(source.uuid, MyType.READY)
async def on_ready(event: Event[MyData]) -> None:
    ...


await app.start_source(source)
```

运行中的 `add_source()` 会立即绑定 `AppContext`，但不会自动启动。这样 Source
不会在订阅建立前产生事件。

## 暂停与恢复

```python
await app.stop_source(source)
# Source 仍被注册，订阅也保留。
await app.start_source(source.uuid)
```

`BaseSource.start()` 和 `stop()` 对重复调用是幂等的。具体扩展仍应保证
`on_start()`/`on_stop()` 正确重建和释放自身资源。

## 移除

```python
removed = await app.remove_source(source.uuid)
```

移除顺序为：

1. 停止 Source；
2. 删除该 UUID 的全部订阅；
3. 从 manager 中摘除。

停止失败或被取消时不会删除订阅和注册，异常原样传播；Source 保持
`cleanup_required`，修正瞬时故障后可再次调用 `remove_source()`。只有停止成功后
才执行退订和摘除。不存在的 UUID 返回 `None`。

## 查找多实例

```python
source = app.get_source(MySource)
source = app.get_source(MySource, config_key="account_a")
source = app.get_source(source_uuid)
```

只按类型查找时返回第一个匹配实例。同类型多账号应为每个实例设置不同
`config_key`，并使用精确查找。

## 生命周期限制

- manager 关闭后，添加或启动 Source 会抛 `LifecycleError`；
- 启动未注册实例会抛 `SourceError`；
- `stop_source()` 不清理订阅；
- `remove_source()` 清理订阅，但不单独关闭共享 API；API 由应用最终关闭。

## 相关页面

- [生命周期](/guide/lifecycle.html)
- [开发自定义 Source](/extensions/source.html)
- [BotApp API](/api/app.html)
