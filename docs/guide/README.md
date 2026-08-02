---
title: 使用指南
---

# 使用指南

本栏目面向第一次接触 ButterBot 的开发者，目标是从环境准备走到一个能够
启动、收到事件并正常关闭的异步应用。

## 推荐阅读顺序

1. [项目介绍](./introduction.md)：确认项目解决的问题和能力边界。
2. [安装](./installation.md)：准备 Python 与项目依赖。
3. [快速开始](./quick-start.md)：运行不依赖外部服务的闭环示例。
4. [项目结构](./project-structure.md)：理解公共门面与内部模块。
5. [生命周期](./lifecycle.md)：选择 `run()`、`async with` 或手动控制。
6. [运行模式与 `run()`](./runtime-modes.md)：理解 `cli_mode`、信号和阻塞语义。
7. [命令行](./cli.md)：检查配置并管理本地应用进程。

::: tip 已有异步应用
如果调用方已经拥有事件循环，阅读[生命周期](./lifecycle.md)和
[运行模式与 `run()`](./runtime-modes.md)，不要在协程中调用 `BotApp.run()`。
:::

完成本栏目后，可继续阅读[核心概念](/concepts/)或直接配置
[NapCat / Bilibili 事件源](/features/)。
