---
title: 飞书
---

# 飞书

## 本页目标

使用官方 SDK 的 WebSocket 长连接接收飞书 v2.0 事件，并调用常用 IM OpenAPI。
事件接收不提供 Webhook 模式。

## 前置条件

- 安装 `butterbot-python[lark]`；
- 创建企业自建应用并启用机器人能力；
- 在开发者后台把事件订阅方式设置为“使用长连接接收事件”；
- 添加需要的事件和权限，然后发布应用版本。

飞书长连接只支持企业自建应用。事件处理需要在 3 秒内完成，多个同应用连接按
集群模式随机投递而不是广播。飞书采用至少一次投递，ButterBot 默认按
`header.event_id` 在单进程内去重。

官方参考：[使用长连接接收事件](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-configure-/request-url-configuration-case)、
[事件列表](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-list)、
[机器人自定义菜单事件](https://open.feishu.cn/document/client-docs/bot-v3/events/menu)。

## 配置

```yaml
environment:
  LARK_APP_ID: ""
  LARK_APP_SECRET: ""

sources:
  feishu_bot:
    source_name: lark
    kwarg:
      LarkSource: {}
    app_id: "${LARK_APP_ID}"
    app_secret: "${LARK_APP_SECRET}"
    ready_timeout: 30.0
    request_timeout: 30.0
    deduplicate_events: true
    dedup_ttl: 3600.0
    dedup_max_entries: 4096
    # 尚无专用 Data 模型的 v2.0 事件可在这里注册：
    custom_event_types:
      - contact.user.created_v3
```

`verification_token` 和 `encrypt_key` 可配置，但 WebSocket 长连接在建连时完成鉴权，
不会像 Webhook 一样要求业务代码解密和验签。不要提交真实 `app_secret`。

## 订阅事件

```python
from butterbot.app import BotApp
from butterbot.sources.lark import LarkSource, LarkType
from butterbot.sources.lark.events import (
    LarkMenuEvent,
    LarkMessageReceiveEvent,
)

app = BotApp()
source = app.get_source(LarkSource, "feishu_bot")
assert source is not None


@app.subscribe(source.uuid, LarkType.MESSAGE_RECEIVE)
async def on_message(event: LarkMessageReceiveEvent) -> None:
    print(event.data.message.chat_id, event.data.message.text)
    await event.data.reply_text("收到")


@app.subscribe(source.uuid, LarkType.MENU)
async def on_menu(event: LarkMenuEvent) -> None:
    print(event.data.event_key, event.data.operator.operator_id.open_id)


app.run()
```

`LarkType.MESSAGE`、`REACTION`、`CHAT` 和 `MEMBER` 是父级订阅规则，可匹配
相应子事件。额外注册的 `custom_event_types` 使用 `LarkType.UNKNOWN`，原始载荷
保存在 `event.data.raw_data`。

## 调用 API

```python
from butterbot.sources.lark import LarkApi

api = app.get_api(LarkApi, "feishu_bot")

result = await api.send_text("oc_chat_id", "hello")
await api.reply_text("om_message_id", "收到", reply_in_thread=False)
await api.add_reaction("om_message_id", "THUMBSUP")
```

`send_message()` 对应官方[发送消息](https://open.feishu.cn/document/server-docs/im-v1/message/create)
接口。`content` 可传已编码 JSON 字符串或映射；映射由 API 封装统一编码。
`send_text()`、`send_post()` 与 `send_card()` 是常用消息类型的便捷方法。

所有内置事件的 `LarkType → Data → Event` 对照、嵌套字段，以及发送、回复、更新、
撤回、reaction 和文件上传调用见
[飞书 Data 与 API](./api-usage.md#飞书顶层导出)。

## 关闭与错误

`LarkSource.stop()` 会关闭 WebSocket、取消协议心跳和接收任务，并停止内部事件
消费者；`LarkApi.aclose()` 可被应用关闭流程重复调用。连接中断时 Source 健康状态
变为 `DEGRADED`，重连成功后恢复 `READY`。

OpenAPI 返回非零错误码时抛出 `LarkApiError`。排障时优先记录异常上的 `code` 和
`log_id`；权限不足、机器人不在群内、接收 ID 类型错误都属于常见原因。
