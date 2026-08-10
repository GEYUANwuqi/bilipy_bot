---
title: SourceManager
---

# SourceManager

`SourceManager` 由 `BotApp.source_manager` 暴露。应用代码优先使用 BotApp 的同名转发
方法；高级扩展可以读取以下稳定成员：

| 成员 | 说明 |
| --- | --- |
| `sources` | UUID 到 Source 的只读副本 |
| `running` / `closing` / `closed` | 生命周期状态 |
| `source_catalog` | Source 逻辑目录 |
| `add_source(...)` | 登记但不自动启动 Source |
| `get_source(...)` / `get_sources(...)` | 按 UUID、类型或 `SourceRef` 查询 |
| `start_source(...)` / `stop_source(...)` | 运行期启停单个 Source |
| `remove_source(uuid)` | 停止、退订并移除 Source |
| `start()` / `stop()` / `close()` | 批量生命周期 |

`discard_unstarted_source()` 是构造期回滚接口，不建议业务代码使用。
