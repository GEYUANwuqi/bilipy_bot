---
title: 扩展开发
---

# 扩展开发

本栏目面向接入新平台或新数据输入的开发者。

- [开发 Source](./source.md)
- [开发 API](./api.md)
- [Data 与 Type](./data-and-types.md)
- [开发 Filter](./filters.md)
- [测试异步扩展](./testing.md)
- [实验性插件系统](./plugins.md)
- [插件原型基础](./prototype-foundations.md)

仓库提供可信代码、显式启用、仅启动期加载的 provisional 插件系统。它支持独立
wheel 的发现、依赖顺序、两阶段注册和失败回滚，但不是安全沙箱，也不支持热重载或
运行期卸载。一个完整适配通常仍由 Source、API、Data、Type 和可选 Filter 组成。
