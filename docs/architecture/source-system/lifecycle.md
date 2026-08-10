---
title: Source 生命周期
---

# Source 生命周期

`BaseSource.start()` / `stop()` 是框架拥有的模板方法，子类只实现 `on_start()` 和
`on_stop()`。启动前由 `SourceManager` 注入 `AppContext`；启动失败会尝试回滚部分
资源，停止失败则保留清理责任，允许后续重试。

Source 创建的 task、连接和线程必须由同一个 Source 保存并关闭。应用关闭时先停止
生产者，再排空 EventBus，最后关闭 API，避免关闭途中继续产生事件。

完整状态与扩展契约见 [BaseSource API](/api/source/base-source.md)。
