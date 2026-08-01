---
title: Bilibili
---

# Bilibili

## 本页目标

选择 Bilibili 动态、直播状态或直播弹幕 Source，并理解它们不同的并发模型。
使用前先安装 `uv add "butterbot-python[bilibili]"`; 该 extra 显式包含
`bilibili-api-python` 和 `aiohttp`.

## 配置

`source_name: bilibili` 会把实例配置构建为 `bilibili_api.Credential`：

```yaml
sources:
  bili_account:
    source_name: bilibili
    kwarg:
      BiliDynamicSource:
        watch_targets: [123456]
        poll_interval: 60
      BiliLiveSource:
        watch_targets: [123456]
        poll_interval: 20
      BiliDanmakuSource:
        room_id: [123456]
    sessdata: "${BILI_SESSDATA:-}"
    bili_jct: "${BILI_JCT:-}"
    buvid3: "${BILI_BUVID3:-}"
```

是否必须提供有效登录凭证取决于上游接口。`BiliDanmakuSource` 启动时要求
`config_key` 对应的配置存在；部分 `BilibiliApi` 方法可接收空凭证，而
`get_new_dynamic_list()` 明确要求凭证。

## 动态轮询

```python
from butterbot.sources.bilibili import BiliDynamicSource, DynamicType

source = app.get_source(BiliDynamicSource, "bili_account")
assert source is not None


@app.subscribe(source.uuid, DynamicType.NEW)
async def on_new_dynamic(event: Event[DynamicData]) -> None:
    print(event.data)
```

状态包括 `NEW`、`DELETED`、`NULL` 和订阅通配 `ALL`。首次获取没有旧值时状态为
`NULL`。

## 直播状态轮询

```python
from butterbot.sources.bilibili import BiliLiveSource, LiveType

source = app.get_source(BiliLiveSource, "bili_account")
assert source is not None
```

状态包括 `ONLINE`、`OFFLINE`、`OPEN`、`CLOSE`、`NULL` 和 `ALL`。
`BiliDynamicSource` 与 `BiliLiveSource` 每轮依次处理当前目标快照，完成一整轮后
只等待一次 `poll_interval`。目标为空时内部等待 5 秒。

可在运行期更新：

```python
source.add_members([111, 222])
source.remove_members([111])
source.set_poll_interval(60)
```

非正间隔不会生效；30 秒及以下会记录请求频率警告。

## 直播弹幕

```python
from butterbot.sources.bilibili import BiliDanmakuSource, DanmakuType

source = app.get_source(BiliDanmakuSource, "bili_account")
assert source is not None


@app.subscribe(source.uuid, DanmakuType.DANMAKU)
async def on_danmaku(event: Event[DanmakuMsgData]) -> None:
    print(event.data)
```

为兼容旧代码，构造器仍接受 `room_id=[...]`；不能同时传 `room_id` 和
`watch_targets`。弹幕源为每个房间创建专用线程和事件循环，并把事件线程安全地
调度回 BotApp 所在主循环。一房间一线程是对上游 WebSocket 监听缺陷的
稳定性隔离边界，不会被合并成主 loop task。每个受管 worker 统一持有
thread、loop、connect task 和 ready/error/closed 信号；多房间启动只有在全部
认证 ready 后才成功，任一失败会回滚所有线程。

`room_ready_timeout` 和 `room_stop_timeout` 分别控制单房间就绪与关闭上限。
动态房间方法均需要 `await`：

```python
await source.add_new_room(123456)
await source.stop_room(123456)
await source.start_room(123456)
await source.remove_room(123456)
```

## 任务与错误边界

- 两个轮询 Source 拥有自己的 monitor task，停止时取消并等待；
- 单目标轮询失败会记录日志并继续后续目标/轮次；
- 弹幕 Source 会消费 connect/publish Future 结果；停止超时会向上抛出并
  保留 worker 以便再次清理；
- 平台请求、字段和限流行为由 `bilibili-api-python` 与远端服务决定。

完整示例：

- [`examples/plugins/example.bilibili-manager/`](https://github.com/GEYUANwuqi/ButterBot/tree/dev_main/examples/plugins/example.bilibili-manager)
- [`examples/live_danmaku_example.py`](https://github.com/GEYUANwuqi/ButterBot/blob/dev_main/examples/live_danmaku_example.py)
