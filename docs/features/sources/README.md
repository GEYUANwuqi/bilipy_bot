---
title: 事件源介绍
---

# 事件源介绍

事件源负责连接外部系统、把平台数据转换为 ButterBot `Event`，并通过事件总线
发布。应用代码通常只需要选择 Source、配置账号、订阅对应 `Type`，不需要直接
管理底层连接任务。

## 内置事件源

| 平台 | Source | 主要能力 | 接入指南 |
| --- | --- | --- | --- |
| NapCat | `NapcatSource` | OneBot 消息、通知、请求与 action API | [NapCat](./napcat.md) |
| Bilibili | `BiliDynamicSource` 等 | 动态、直播状态和直播弹幕 | [Bilibili](./bilibili.md) |
| 飞书 | `LarkSource` | WebSocket 事件与常用 IM OpenAPI | [飞书](./lark.md) |

每个 Source 都有独立 `uuid`，订阅通过这个 ID 隔离不同实例。`config_key` 则把
Source 与对应账号的配置和 API 单例关联起来，因此同一平台可以配置多个账号。

## 使用路径

1. 在 YAML 的 `sources.<config_key>` 下选择 `source_name`；
2. 通过 `kwarg.<SourceClassName>` 自动创建 Source，或在代码中调用
   `app.add_source()`；
3. 获取 Source 并使用它声明的 `Type` 注册订阅；
4. 需要主动操作平台时，通过 `app.get_api()` 获取同一配置键的 API。

完整配置和代码以各平台页面为准。应用启动后增删、暂停或恢复 Source，参见
[运行期事件源管理](./runtime-management.md)；常用调用方式参见
[事件源 Data / API](./api-usage.md)。

## 内容边界

本栏目只说明如何配置和使用事件源。编写新 Source 的契约与测试方式属于
[扩展开发](/extensions/custom-source.html)，任务所有权、启动回滚和 `SourceManager`
内部控制流属于[框架开发](/architecture/)。
