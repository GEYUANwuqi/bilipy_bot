---
title: SourceManager
---

# SourceManager

`SourceManager` 负责 Source 的登记、上下文绑定、批量启停和运行期增删，不负责关闭
EventBus 或 API registry。逻辑目录同时维护 `source_kind + config_key` 与 UUID 的
映射，供 `SourceRef` 查询。

运行中新增 Source 采用显式三步：注册、订阅、启动。这样订阅建立前不会抢先产生
事件。移除时则先停止 Source，再撤销其订阅，最后删除登记；停止失败时保留入口以便
重试。

公开操作通常由 `BotApp` 转发，见 [SourceManager API](/api/source/source-manager.md)。
