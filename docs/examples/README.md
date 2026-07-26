---
title: 示例与最佳实践
---

# 示例与最佳实践

示例按可验证程度分类：

| 示例 | 分类 | 自动验证 |
| --- | --- | --- |
| `minimal_source_example.py` | 可直接执行的完整示例 | 子进程运行并断言退出 |
| `napcat_example.py` | 需要外部服务的完整示例 | 语法与静态契约 |
| `manager_example.py` | 需要外部服务的完整示例 | 语法与静态契约 |
| `live_danmaku_example.py` | 需要外部服务的完整示例 | 语法与静态契约 |

- [无外部依赖的最小示例](./minimal.md)
- [NapCat 示例](./napcat.md)
- [Bilibili 示例](./bilibili.md)

“完整示例”表示文件具备入口和关闭路径，不表示仓库 CI 能访问第三方平台。
需要外部服务的示例不会被标记为已端到端验证。
