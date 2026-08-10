---
title: 故障排除
---

# 故障排除

按发生阶段选择页面：

- [安装与导入](./installation.md)
- [配置、订阅与启动](./runtime.md)
- [异步生命周期与资源](./async-lifecycle.md)

排障时先保留完整异常类型和 traceback，再移除 Token、Cookie、Authorization、
用户 ID 等敏感信息。Handler task 异常写入日志，不一定出现在调用
`publish()` 的栈上。
