---
title: 入门
---

# 入门

本栏目面向第一次接触 ButterBot 的开发者，目标是从环境准备走到一个能够
启动、收到事件并正常关闭的异步应用。

## 推荐阅读顺序

1. [项目介绍](./introduction.md)：确认项目解决的问题和能力边界。
2. [安装](./installation.md)：准备 Python 与项目依赖。
3. [快速开始](./quick-start.md)：运行不依赖外部服务的闭环示例。
4. [项目结构](./project-structure.md)：理解公共门面与内部模块。
5. [基础示例](./basic-example.md)：从完整、可退出的例子理解最小应用。
6. [示例与最佳实践](./best-practices.md)：选择内置平台或插件示例继续实践。

::: tip 已有异步应用
如果调用方已经拥有事件循环，阅读[生命周期](/architecture/lifecycle.md)和
[运行模式](/features/runtime-modes.md)，不要在协程中调用 `BotApp.run()`。
:::

完成本栏目后，可继续阅读[功能指南](/features/)。如果要编写自己的 Source、API
或插件，进入[扩展开发](/extensions/)；维护框架本身时再阅读
[框架开发](/architecture/)。
