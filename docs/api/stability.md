---
title: API 稳定性
---

# API 稳定性

ButterBot 当前处于 `3.1.0.dev2` 的 R1 收敛窗口. 这个窗口采用 clean break:
旧的 provisional API 会直接删除, 不提供 alias、转发模块或弃用包装器. R1 验收
完成并发布稳定版本后, 新的 stable API 才开始受到 SemVer 保护.

## 稳定性分级

### Stable

同时满足以下条件的名称属于 stable API:

- 在 API 文档中列出;
- 从对应门面的 `__all__` 导出;
- 有公开行为测试或外部 wheel fixture 覆盖.

稳定版本发布后, stable API 在同一 major 内不会被删除, 也不会发生破坏现有正确
调用的签名或语义变更. 必须进行破坏性调整时, 通过下一个 major 发布.

### Provisional

文档明确标注 provisional 的 adapter、诊断 DTO 或实验能力可以在 minor 或预发布
版本中调整、重命名或删除. 使用者不应把它们当作长期插件契约.

### Internal

以下内容属于 internal API, 不提供兼容承诺:

- 以下划线开头的模块或名称;
- 未从门面 `__all__` 导出的实现细节;
- 插件 discovery、bootstrap、manager 和 registrar 的框架控制面;
- 测试 helper 与 fixture 内部类型.

能通过深层模块路径 import 不代表该名称是 stable API.

## R1 收敛规则

R1 期间删除旧 API 时, 必须在同一提交中完成以下工作:

1. 删除旧实现和旧导出;
2. 更新全部生产调用、tests、fixtures 和 examples;
3. 更新 API 文档和 changelog;
4. 增加最终 `__all__` snapshot, 并断言旧名称不可再从门面导入;
5. 通过 wheel 与外部插件 fixture smoke.

R1 不新增 warning、alias、兼容 wrapper 或双轨测试. 目标是只留下最终设计.

## 中文文本标点

代码注释、docstring、日志、异常消息、CLI 文案和项目文档继续使用中文内容, 但统一
使用 ASCII 半角标点. 协议 fixture、上游原始 payload、用户数据和必须逐字匹配的
正则不做机械替换.
