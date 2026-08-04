---
title: API 稳定性
---

# API 稳定性

ButterBot `3.1.0` 是正式稳定版。本文定义公开 API 的兼容边界，并适用于应用、Source
扩展、API、数据模型、类型、Filter 和可信 Handler 插件。

## 稳定性分级

### Stable

同时满足以下条件的名称属于 stable API:

- 在 API 文档中列出;
- 从对应门面的 `__all__` 导出;
- 有公开行为测试或外部 wheel fixture 覆盖.

Stable API 在同一 major 内不会被删除，也不会发生破坏现有正确调用的签名或语义变更。
必须进行破坏性调整时，通过下一个 major 发布。

补充功能可以在同一 major 的 minor 版本中新增；兼容性修复和文档修正通过 patch 版本
发布。任何稳定 API 的例外均必须在发布说明中明确写出。

### Experimental

文档明确标注为 experimental 的能力尚未纳入稳定兼容承诺，可在后续 minor 版本调整、
重命名或删除。每次变更仍必须同步 changelog、文档与契约测试；未标注 experimental
的公开名称不得按此规则处理。

### Internal

以下内容属于 internal API, 不提供兼容承诺:

- 以下划线开头的模块或名称;
- 未从门面 `__all__` 导出的实现细节;
- 插件 discovery、可选运行时工厂、manager 和 registrar 的框架控制面;
- 测试 helper 与 fixture 内部类型.

能通过深层模块路径 import 不代表该名称是 stable API.

## 版本与变更规则

修改 stable API 时，必须在同一变更中完成以下工作：

1. 删除旧实现和旧导出;
2. 更新全部生产调用、tests、fixtures 和 examples;
3. 更新 API 文档和 changelog;
4. 更新 `__all__` snapshot, 并对删除或替换结果建立明确断言;
5. 通过 wheel 与外部插件 fixture smoke.

不为尚未公开的 internal 控制面增加兼容 wrapper。若 stable API 必须发生破坏变化，
必须提升 major 版本，并在 changelog 给出迁移路径。

## 中文文本标点

代码注释、docstring、日志、异常消息、CLI 文案和项目文档继续使用中文内容, 但统一
使用 ASCII 半角标点. 协议 fixture、上游原始 payload、用户数据和必须逐字匹配的
正则不做机械替换.
