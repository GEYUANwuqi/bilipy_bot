---
title: 扩展开发
---

# 扩展开发

本栏目同时面向业务插件作者和接入新平台或新数据输入的事件源适配作者。

- [开发 Source](./source.md)
- [开发 API](./api.md)
- [Data 与 Type](./data-and-types.md)
- [开发 Filter](./filters.md)
- [测试异步扩展](./testing.md)
- [实验性插件系统](./plugins.md)

仓库提供可信代码、显式授权、仅启动期加载的 provisional 混合插件系统。它支持
独立 wheel entry point 和无需 Python 包元数据的 `./plugins` 便携目录，统一处理
依赖顺序、Handler 注册、生命周期和失败回滚，但不是安全沙箱，也不支持热重载或
运行期卸载。
一个完整适配通常仍由 Source、API、Data、Type 和可选 Filter 组成。

业务插件从 `butterbot.plugin` 导入插件契约；需要 Event、Filter、Data、Type 或
底层 API 时直接从 `butterbot.core` 导入。Source 由应用拥有，不由插件创建或接管。
