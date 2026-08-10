---
title: 公共工具
---

# 公共工具

`butterbot.utils` 公开以下工具：

| 符号 | 用途 |
| --- | --- |
| `DataPair[T]` | 维护当前值与上一值，便于判断变化 |
| `setup_logging(console_level=None)` | 安装框架日志并返回 `LoggingLease` |
| `LoggingLease` | 可关闭、可作上下文管理器的日志租约 |

WebSocket 客户端和 ANSI helper 当前属于内部基础设施，不因可导入而承诺公共兼容性。
