---
title: API 稳定性
---

# API 稳定性

ButterBot 当前处于 `3.1.0b1` Beta. R1 clean-break 已经结束, 当前 API 用于第三方
Source 和 Handler 插件的真实环境验证. Beta 作者面仍是 provisional, 但公开变更
必须同步 changelog、文档、API snapshot 和外部 wheel fixture, 不能再无记录地删除.

进入 RC 后冻结计划随 `3.1` 正式版发布的作者 API. 正式稳定版本发布后, stable API
开始受到 SemVer 保护.

## 稳定性分级

### Stable

正式版中同时满足以下条件的名称属于 stable API:

- 在 API 文档中列出;
- 从对应门面的 `__all__` 导出;
- 有公开行为测试或外部 wheel fixture 覆盖.

稳定版本发布后, stable API 在同一 major 内不会被删除, 也不会发生破坏现有正确
调用的签名或语义变更. 必须进行破坏性调整时, 通过下一个 major 发布.

### Provisional

当前 Beta 作者面以及文档明确标注 provisional 的 adapter、诊断 DTO 或实验能力,
可以在后续预发布版本中调整、重命名或删除. 每次变更必须记录并同步契约测试;
使用者在 RC 前应使用有上限的版本约束, 不应假设跨 Beta 永久兼容.

### Internal

以下内容属于 internal API, 不提供兼容承诺:

- 以下划线开头的模块或名称;
- 未从门面 `__all__` 导出的实现细节;
- 插件 discovery、可选运行时工厂、manager 和 registrar 的框架控制面;
- 测试 helper 与 fixture 内部类型.

能通过深层模块路径 import 不代表该名称是 stable API.

## Beta 与 RC 收敛规则

Beta 期间调整作者 API 时, 必须在同一提交中完成以下工作:

1. 删除旧实现和旧导出;
2. 更新全部生产调用、tests、fixtures 和 examples;
3. 更新 API 文档和 changelog;
4. 更新 `__all__` snapshot, 并对删除或替换结果建立明确断言;
5. 通过 wheel 与外部插件 fixture smoke.

不为尚未公开的 internal 控制面增加兼容 wrapper. 已进入 Beta 作者面的名称发生破坏
变化时, 必须提升预发布版本并在 changelog 给出替代路径.

RC 只接受发布阻断修复、文档修正和不改变正确调用行为的内部改动. Source 装配、
插件作者面或生命周期语义需要重构时, 应退出 RC 并发布新的 Beta.

## 中文文本标点

代码注释、docstring、日志、异常消息、CLI 文案和项目文档继续使用中文内容, 但统一
使用 ASCII 半角标点. 协议 fixture、上游原始 payload、用户数据和必须逐字匹配的
正则不做机械替换.
