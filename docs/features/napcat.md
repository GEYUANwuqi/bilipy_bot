---
title: NapCat
---

# NapCat

## 本页目标

连接 NapCat WebSocket，订阅 OneBot 事件，并通过同一 API 连接发送请求。

## 前置条件

- 可访问的 NapCat WebSocket 地址；
- 服务器要求认证时准备 Token；
- 已复制并妥善保管本地 `config.yaml`。

```bash
cp examples/config.example.yaml config.yaml
```

## 配置

```yaml
sources:
  qq_account:
    source_name: napcat
    kwarg:
      NapcatSource: {}
    url: "${NAPCAT_URL:-ws://localhost:3001}"
    token: "${NAPCAT_TOKEN:-}"
    heartbeat: 30.0
    reconnect_attempts: 5
    receive_timeout: 60.0
```

`url` 必填；其余字段使用 `NapcatConfig` 默认值。`${NAME:-default}` 从当前环境
读取变量并在缺失时使用默认值。不要把真实 Token 提交到仓库。

## 最小接入

```python
from butterbot.app import BotApp
from butterbot.sources.napcat import NapcatSource, NapcatType
from butterbot.sources.napcat.events import NapcatGroupMessageEvent

app = BotApp()
source = app.get_source(NapcatSource, "qq_account")
assert source is not None


@app.subscribe(source.uuid, NapcatType.GROUP_MESSAGE)
async def on_message(event: NapcatGroupMessageEvent) -> None:
    print(event.data.group_id, event.data.message.plain_text)


app.run()
```

`BotApp()` 默认读取当前工作目录的 `config.yaml`。Source 启动时从
`ApiRegistry` 获取 `NapcatApi`，设置消息 Handler，再启动 WebSocket 客户端。

## 事件层级

`NapcatType` 按 OneBot `post_type` 和二级字段组织：

- `META`：生命周期、心跳；
- `MESSAGE`：群消息、私聊消息；
- `SENT`：自身发送的群/私聊消息；
- `REQUEST`：好友、群请求；
- `NOTICE`：群变更、撤回、戳一戳等通知。

父级类型可匹配子类型。例如 `NapcatType.MESSAGE` 同时匹配群消息和私聊消息。
`butterbot.sources.napcat.events` 提供 `Event[具体 Data]` 的类型别名。

## 调用 API

```python
from butterbot.sources.napcat import NapcatApi

api = app.get_api(NapcatApi, "qq_account")
result = await api.send_group_message(
    group_id=123456,
    message=[{"type": "text", "data": {"text": "hello"}}],
)
```

`send_request()` 为每个请求生成 `echo`，等待对应响应。等待超过
`receive_timeout` 会抛 `TimeoutError`；调用被取消时会传播
`CancelledError`，并清理 pending Future。

## 关闭行为

`NapcatSource.on_stop()` 停止 `NapcatApi`；应用随后还会调用
`NapcatApi.aclose()`。客户端关闭实现是幂等的，会取消消息处理 task、
待响应 Future、监听器和 WebSocket。

## 常见问题

- `ConfigError: 缺少配置键 'qq_account'`：检查 `sources` 实例键、Source 的
  `config_key` 和启动工作目录；
- 连接失败：先独立确认 NapCat 地址、端口和认证配置；
- Handler 不触发：使用具体 `NapcatType`，并确认过滤器未拦截；
- 请求超时：确认连接仍在运行且服务器返回相同 `echo`。

完整平台示例见
[`examples/napcat_example.py`](https://github.com/GEYUANwuqi/ButterBot/blob/dev_main/examples/napcat_example.py)。
