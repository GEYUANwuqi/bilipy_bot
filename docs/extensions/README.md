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
- [插件原型基础](./prototype-foundations.md)

当前没有自动发现或加载第三方包的通用 Plugin 系统。仓库只提供 provisional 的
逻辑 Source 引用、注册所有权和手工事务 registrar，用于验证未来插件契约。一个
完整适配通常仍由 Source、API、Data、Type 和可选 Filter 组成。
