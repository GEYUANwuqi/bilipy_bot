---
title: 内置事件源 API
---

# 内置事件源 API

NapCat API 需要 `butterbot-python[napcat]`, Bilibili API 需要
`butterbot-python[bilibili]`. 两个 extra 都显式包含 `aiohttp`.

## NapCat 顶层导出

```python
from butterbot.sources.napcat import (
    NapcatApi,
    NapcatConfig,
    NapcatSource,
    NapcatType,
)
```

### `NapcatConfig`

```python
@dataclass
class NapcatConfig:
    url: str
    token: str | None = None
    heartbeat: float = 30.0
    reconnect_attempts: int = 5
    receive_timeout: float = 60.0
```

### `NapcatSource`

继承 `BaseSource`，构造签名：

```python
NapcatSource(uuid: UUID | None = None, *, config_key: str | None = None)
```

默认 `config_key = "napcat"`，`supported_types = NapcatType`。

### `NapcatApi`

```python
NapcatApi.create(ctx, config_key: str = "napcat") -> NapcatApi
set_handler(handler) -> None
async start() -> None
async stop() -> None
async aclose() -> None
get_metrics() -> dict
async send_request(message: dict) -> dict | None
async call_action(action: str, **params: Any) -> dict | None
async send_group_message(
    group_id: int,
    message: list[dict] | NapcatMessage,
) -> dict | None
async send_forward_message(
    message_type: Literal["group", "private"],
    target_id: str | int,
    message: NapcatForwardMessage,
) -> dict | None
```

`create()` 缺配置抛 `ConfigError`。Handler 必须是协程函数。请求可能抛
`TimeoutError` 或 `CancelledError`。`send_forward_message()` 支持 `group` 和
`private`，其他 `message_type` 会抛出 `ValueError`。

`call_action()` 统一生成 `{"action": action, "params": params}` 请求；业务接口
均通过它调用 NapCat。首批高频适配包括：

```python
# 消息
send_private_message(user_id, message)
delete_message(message_id)
send_like(user_id, times=1)
set_message_emoji_like(message_id, emoji_id, set=True)
mark_group_messages_as_read(group_id)
mark_private_messages_as_read(user_id)
send_poke(group_id, user_id)
friend_poke(user_id)

# 查询
get_login_info()
get_stranger_info(user_id)
get_friend_list()
get_group_list()
get_group_info(group_id)
get_group_member_info(group_id, user_id)
get_group_member_list(group_id)
get_message(message_id)
get_group_message_history(group_id, message_seq=None, count=20)
get_private_message_history(user_id, message_seq=None, count=20)
get_status()
get_version_info()

# 群管理与请求处理
set_group_kick(group_id, user_id, reject_add_request=False)
set_group_ban(group_id, user_id, duration=1800)
set_group_whole_ban(group_id, enable=True)
set_group_admin(group_id, user_id, enable=True)
set_group_card(group_id, user_id, card="")
set_group_name(group_id, name)
set_group_leave(group_id, is_dismiss=False)
set_group_special_title(group_id, user_id, special_title="")
set_friend_add_request(flag, approve=True, remark="")
set_group_add_request(flag, sub_type, approve=True, reason="")
```

这些方法当前返回 NapCat 原始响应 `dict | None`。尚未列出的 action 可通过
`call_action()` 调用；`send_request()` 保留为底层完整请求入口。

### `NapcatMessageBuilder`

`butterbot.sources.napcat.data` 导出 `NapcatMessageBuilder` 和
`NapcatMessage`。builder 为消息段提供显式参数签名，并可链式追加：

```python
from butterbot.sources.napcat.data import NapcatMessageBuilder

message = (
    NapcatMessageBuilder()
    .at_all()
    .text("hello")
    .face("14")
    .image("image.png", image_type="flash")
    .build()
)
```

公开参数可使用面向调用者的名称，例如 `face_id`、`image_type` 和
`message_id`；builder 会将其映射为 OneBot Data 字段。`build()` 返回独立的
`NapcatMessage`，可直接传给 `send_group_message()`。

普通消息 builder 不提供 `forward()` 或 `node()`；可发送的合并转发消息使用
独立的 `NapcatForwardMessageBuilder`：

```python
from butterbot.sources.napcat.data import (
    NapcatForwardMessageBuilder,
    NapcatMessageBuilder,
)

content = NapcatMessageBuilder().text("转发正文")
forward_message = (
    NapcatForwardMessageBuilder(user_id=123456, nickname="示例用户")
    .node(content)
    .forward(message_id=10001)
    .build()
)
```

`node()` 构造自定义作者节点，`forward()` 通过消息 ID 引用已有消息；`build()`
返回只包含转发 node 的 `NapcatForwardMessage`，可通过以下方式发送：

```python
await api.send_forward_message(
    message_type="group",
    target_id=123456,
    message=forward_message,
)
```

### `NapcatType`

公开枚举成员包括 `ALL`、`UNKNOWN`、`META`、`MESSAGE`、`SENT`、`REQUEST`、
`NOTICE` 及其具体子状态。以源码
`butterbot/sources/napcat/types/napcat_type.py` 为完整清单。

### 事件类型别名

`butterbot.sources.napcat.events` 提供 `NapcatEvent`、
`NapcatGroupMessageEvent`、`NapcatNoticeEvent` 等 `TypeAlias`。它们在运行时
仍是参数化 `Event`，主要用于类型注解。

### Data 与 Filter

`butterbot.sources.napcat.data.__all__` 导出 OneBot 事件模型和消息段模型；
`butterbot.sources.napcat.filters` 导出 `GroupFilter`、`UserFilter`、
`SenderRoleFilter`、`TextFilter`、`CommandFilter`、`PrefixFilter`。

## Bilibili 顶层导出

```python
from butterbot.sources.bilibili import (
    BiliDanmakuSource,
    BiliDynamicSource,
    BiliLiveSource,
    BilibiliApi,
    DanmakuType,
    DynamicType,
    LiveType,
)
```

### Source 签名

```python
BiliDynamicSource(
    poll_interval: float | int = 60,
    watch_targets: list[int] | None = None,
    *,
    uuid: UUID | None = None,
    config_key: str | None = None,
)

BiliLiveSource(
    poll_interval: float | int = 20,
    watch_targets: list[int] | None = None,
    *,
    uuid: UUID | None = None,
    config_key: str | None = None,
)

BiliDanmakuSource(
    room_id: list[int] | None = None,
    debug: bool = False,
    *,
    watch_targets: list[int] | None = None,
    room_ready_timeout: float = 20.0,
    room_stop_timeout: float = 10.0,
    uuid: UUID | None = None,
    config_key: str | None = None,
)
```

轮询 Source 公开 `add_members()`、`remove_members()`、
`set_poll_interval()`、`watch_targets` 和 `poll_num`。动态源另有 `members`，
直播源另有 `rooms`。

弹幕 Source 保留一房间一线程的上游兼容边界，但每个房间由受管
worker 统一持有 thread、event loop、connect task 和 ready/error/closed 信号。
`start_room()`、`add_new_room()`、`stop_room()` 和 `remove_room()` 是异步方法；
启动返回时已经认证 ready，停止使用异步跨线程等待，不阻塞主 loop。

### `BilibiliApi`

```python
BilibiliApi.create(ctx, config_key: str = "bilibili") -> BilibiliApi
credential: Credential | None
async get_all_dynamic(uid: int, offset: str = "") -> list[DynamicData]
async get_new_dynamic(uid: int) -> DynamicData
async get_new_dynamic_list() -> list[DynamicData]
async get_room_info(room_id: int) -> LiveRoomData
get_live_danmaku(room_id: int) -> LiveDanmaku
```

数据缺失、DTO 构建失败或凭证缺失时，当前实现可能抛 `ValueError`；上游 SDK
异常原样传播。

### Data

`butterbot.sources.bilibili.data` 导出动态、直播间、弹幕、礼物、上舰和视频分段
领域对象。DTO 包位于 `data.dto`，面向适配器解析，不作为普通 Handler 的首选
导入路径。
