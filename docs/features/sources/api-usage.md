---
title: 事件源 API 使用
---

# 事件源 Data 与 API

NapCat API 需要 `butterbot-python[napcat]`，Bilibili API 需要
`butterbot-python[bilibili]`，飞书 API 需要 `butterbot-python[lark]`。
NapCat 和 Bilibili extra 都显式包含 `aiohttp`。

## 通用调用方式

平台 API 都由 `ApiRegistry` 按“API 类型 + `config_key`”缓存。应用代码从
`BotApp` 获取；NapCat 和飞书 Data 还会在发布时绑定同账号 API：

```python
# 应用主动调用
api = app.get_api(PlatformApi, "account_name")

# Handler 内调用；仅适用于 NapCat / 飞书 Source 发布并绑定过的 Data
api = event.data.api
```

相同类型和配置键会得到同一实例。不要手工构造需要连接的 API，也不要在 Handler
中调用 `start()` / `stop()`；连接生命周期由 Source 和 `BotApp.close()` 管理。
手工构造、未经过 Source 发布的 NapCat / 飞书 Data 没有运行时绑定，访问
`data.api` 会抛出 `RuntimeError`。Bilibili Data 不提供 `api` 属性，始终通过
`app.get_api(BilibiliApi, config_key)` 获取。

## 飞书顶层导出

```python
from butterbot.sources.lark import (
    LarkApi,
    LarkApiError,
    LarkConfig,
    LarkSource,
    LarkType,
)
```

`LarkSource` 只用 WebSocket 长连接接收事件。`LarkApi` 的消息发送、回复、
更新、撤回、查询、reaction 及文件上传使用飞书 OpenAPI；失败时抛出带
`code`、`message` 和 `log_id` 的 `LarkApiError`。

首批事件包括消息接收/已读/撤回、reaction 新增/删除、群更新/解散、用户和
机器人进出群、撤销拉人、用户进入机器人单聊以及机器人自定义菜单。
`custom_event_types` 可注册额外 v2.0 事件，这些事件以 `LarkType.UNKNOWN` 发布，
完整 envelope 位于 `event.data.raw_data`。

### 飞书事件数据模型

Data 从 `butterbot.sources.lark.data` 导入，`Event[Data]` 类型别名从
`butterbot.sources.lark.events` 导入。所有事件都继承 `LarkData`，共有：

| 字段或属性 | 类型 | 说明 |
| --- | --- | --- |
| `header` | `LarkEventHeader` | `event_id`、`event_type`、创建时间和租户信息 |
| `raw_data` | `dict[str, Any]` | 未裁剪的飞书 v2.0 envelope |
| `config_key` | `str` | 产生事件的账号配置键 |
| `api` | `LarkApi` | 同一账号的 API 实例 |

内置事件到领域模型的映射：

| `LarkType` | Data / Event 别名 | 主要业务字段 |
| --- | --- | --- |
| `MESSAGE_RECEIVE` | `LarkMessageReceiveData` / `LarkMessageReceiveEvent` | `sender`、`message` |
| `MESSAGE_READ` | `LarkMessageReadData` / `LarkMessageReadEvent` | `reader`、`message_id_list` |
| `MESSAGE_RECALLED` | `LarkMessageRecalledData` / `LarkMessageRecalledEvent` | `message_id`、`chat_id`、`recall_time` |
| `REACTION_CREATED` | `LarkReactionCreatedData` / `LarkReactionCreatedEvent` | `message_id`、`reaction_type`、`user_id` |
| `REACTION_DELETED` | `LarkReactionDeletedData` / `LarkReactionDeletedEvent` | 与新增 reaction 相同 |
| `CHAT_UPDATED` | `LarkChatUpdatedData` / `LarkChatUpdatedEvent` | `chat_id`、`before_change`、`after_change` |
| `CHAT_DISBANDED` | `LarkChatDisbandedData` / `LarkChatDisbandedEvent` | `chat_id`、`name`、`operator_id` |
| `BOT_P2P_CHAT_ENTERED` | `LarkBotP2pChatEnteredData` / 对应 Event 别名 | `chat_id`、`last_message_id` |
| `USER_ADDED` | `LarkUserAddedData` / `LarkUserAddedEvent` | `chat_id`、`users` |
| `USER_DELETED` | `LarkUserDeletedData` / `LarkUserDeletedEvent` | `chat_id`、`users` |
| `USER_WITHDRAWN` | `LarkUserWithdrawnData` / `LarkUserWithdrawnEvent` | `chat_id`、`users` |
| `BOT_ADDED` | `LarkBotAddedData` / `LarkBotAddedEvent` | `chat_id`、群名称与操作者 |
| `BOT_DELETED` | `LarkBotDeletedData` / `LarkBotDeletedEvent` | 与机器人入群相同 |
| `MENU` | `LarkMenuData` / `LarkMenuEvent` | `event_key`、`operator`、`timestamp` |
| `UNKNOWN` | `LarkUnknownData` / `LarkUnknownEvent` | `event_type_name`、`raw_data` |

`LarkMessage` 提供 `message_id`、`chat_id`、`chat_type`、`message_type`、原始
`content` 和 `mentions`；`content_data` 把 JSON 内容解析为字典，`text` 安全读取
文本正文。用户标识统一使用 `LarkUserId`，其中 `user_id`、`open_id`、`union_id`
都可能为空，应按应用权限和事件类型选择。

消息事件有同账号快捷调用：

```python
@app.subscribe(source.uuid, LarkType.MESSAGE_RECEIVE)
async def on_message(event: LarkMessageReceiveEvent) -> None:
    data = event.data
    print(data.sender.sender_id.open_id, data.message.text)
    await data.reply_text("收到")
    await data.send_text("这是一条不引用原消息的新消息")
```

### 飞书 API 调用

常用方法及返回值：

| 方法 | 用途 |
| --- | --- |
| `send_message(receive_id, msg_type, content, ...)` | 发送任意消息类型 |
| `send_text()` / `send_post()` / `send_card()` | 发送文本、富文本或交互卡片 |
| `reply_message()` / `reply_text()` | 引用回复，可选择话题内回复 |
| `update_message(message_id, content)` | 更新机器人发送的消息 |
| `delete_message(message_id)` | 撤回机器人发送的消息 |
| `get_message(message_id, ...)` | 获取消息详情 |
| `add_reaction()` / `delete_reaction()` | 新增或删除表情回复 |
| `upload_image()` / `upload_file()` | 上传资源并取得 `image_key` / `file_key` |

所有 OpenAPI 方法返回飞书响应的 `data` 字典，平台返回非零错误码时抛
`LarkApiError`。可记录其 `code`、`message` 和 `log_id` 定位权限或参数问题。

```python
api = app.get_api(LarkApi, "feishu_bot")

# 默认按 chat_id 发送；给用户发送时显式指定标识类型
await api.send_text("oc_chat_id", "群消息")
await api.send_text(
    "ou_open_id",
    "私聊消息",
    receive_id_type="open_id",
)

await api.reply_text("om_message_id", "收到", reply_in_thread=True)
await api.update_message("om_message_id", {"text": "更新后的文本"})
await api.add_reaction("om_message_id", "THUMBSUP")

with open("image.png", "rb") as image_file:
    uploaded = await api.upload_image(image_file)
await api.send_message(
    "oc_chat_id",
    "image",
    {"image_key": uploaded["image_key"]},
)
```

完整方法形态：

```python
send_message(receive_id, msg_type, content, *, receive_id_type="chat_id", uuid=None)
reply_message(message_id, msg_type, content, *, reply_in_thread=False, uuid=None)
get_message(message_id, *, user_id_type="open_id")
upload_image(image, *, image_type="message")
upload_file(file, *, file_type, file_name, duration=None)
```

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

### NapCat 事件便捷方法

`NapcatSource` 会在发布事件前把 `AppContext` 和当前
`config_key` 绑定到 `NapcatData`。因此订阅者可以通过
`event.data.api` 取得对应账号的 `NapcatApi`，也可以直接使用事件
上的便捷方法：

```python
@app.subscribe(napcat_id, NapcatType.GROUP_MESSAGE)
async def handle_message(event: NapcatGroupMessageEvent):
    data = event.data
    await data.reply("收到")              # 默认引用原消息
    await data.set_emoji_like(66)
    await data.mark_read()
```

快捷方法包括：

- 群消息：`reply()`、`recall()`、`set_emoji_like()`、`mark_read()`、
  `poke()`
- 私聊消息：`reply()`、`recall()`、`set_emoji_like()`、`mark_read()`、
  `poke()`、`like()`
- 戳一戳通知：`poke_back()`
- 好友和加群请求：`approve()`、`reject()`

`reply()` 接受字符串、原始消息段列表或 `NapcatMessage`；传入
`quote=False` 可不引用原消息。手动构造而未经 `NapcatSource`
发布的 Data 不具备运行时上下文，调用 `api`、`runtime` 或便捷
方法会抛出 `RuntimeError`。

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

所有事件 Data 都继承 `NapcatData`，共有 `time`、`self_id`、`post_type`，以及由
Source 绑定的 `runtime`、`config_key`、`bus`、`api`。常用模型如下：

| 事件类别 | Data | 主要字段 |
| --- | --- | --- |
| 群消息 | `NapcatGroupMessageData` | `message_id`、`group_id`、`user_id`、`sender`、`message` |
| 私聊消息 | `NapcatPrivateMessageData` | `message_id`、`user_id`、`target_id`、`sender`、`message` |
| 自身发送 | `NapcatGroupMessageSentData`、`NapcatPrivateMessageSentData` | 目标、消息段与发送者 |
| 群变更通知 | `NapcatGroupIncreaseNoticeData`、`NapcatGroupDecreaseNoticeData` 等 | `group_id`、`operator_id`、`user_id` |
| 撤回与 reaction | `NapcatGroupRecallNoticeData`、`NapcatReactionNoticeData` 等 | `message_id` 及操作者或表情信息 |
| 好友请求 | `NapcatFriendRequestData` | `flag`、`user_id`、`comment` |
| 加群请求 | `NapcatGroupRequestData` | `flag`、`group_id`、`sub_type`、`comment` |
| 生命周期与心跳 | `NapcatLifecycleMetaData`、`NapcatHeartbeatMetaData` | `sub_type` 或 `status`、`interval` |

`NapcatMessage` 是消息段列表模型，支持 `plain_text`、`texts()`、`ats()`、
`imgs()` 和 `filter(NodeType)`。例如：

```python
from butterbot.sources.napcat.data import AtNode, ImageNode

@app.subscribe(source.uuid, NapcatType.GROUP_MESSAGE)
async def on_group_message(event: NapcatGroupMessageEvent) -> None:
    data = event.data
    print(data.sender.nickname, data.message.plain_text)
    mentions = data.message.filter(AtNode)
    images = data.message.filter(ImageNode)
    if mentions or images:
        await data.reply("收到包含 @ 或图片的消息")
```

API 可以通过 `app.get_api(NapcatApi, config_key)` 或 `event.data.api` 使用。便捷方法
返回 NapCat 原始响应 `dict | None`；需要检查平台业务状态时，应读取响应中的
`status`、`retcode` 和 `data`，不要只依赖返回值是否为 `None`。

```python
api = app.get_api(NapcatApi, "qq_account")

login = await api.get_login_info()
members = await api.get_group_member_list(123456)
await api.send_private_message(654321, NapcatMessageBuilder().text("你好").build())

# 尚未封装的 action
raw = await api.call_action(
    "set_group_sign",
    group_id=123456,
)
```

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

Source 发布的状态与 Data 映射：

| Source / 状态 | Data | 常用字段 |
| --- | --- | --- |
| `BiliDynamicSource` / `DynamicType.*` | `DynamicData` | `dynamic_id`、`author`、`text`、`pics_url`、`video`、`article`、`forward_orig` |
| `BiliLiveSource` / `LiveType.*` | `LiveRoomData` | `room_info`、`anchor_info`、`watched_show`、`notice_board` |
| `DanmakuType.DANMAKU` | `DanmakuMsgData` | `room_display_id`、`message`、`uid`、`username`、`medal` |
| `DanmakuType.GIFT` | `DanmakuGiftData` | `gift_name`、`gift_num`、`total_coin`、`uname`、`medal`、`blind_gift` |
| `DanmakuType.GUARD` | `DanmakuGuardData` | `username`、`guard_level`、`guard_name`、`num`、`price` |
| `DanmakuType.OPEN` | `LiveRoomData` | 与直播状态模型相同 |

模型是冻结 dataclass。`DynamicData` 的 `video`、`music`、`article`、`live_rcmd`
根据动态类型择一出现；访问前应判断是否为 `None`。`LiveRoomData.room_info`
提供 `jump_url`、直播状态、分区和在线人数；弹幕事件同时保留展示房间号与真实
房间号。

```python
from butterbot.app import Event
from butterbot.sources.bilibili.data import DanmakuGiftData, DynamicData

@app.subscribe(dynamic_source.uuid, DynamicType.NEW)
async def on_dynamic(event: Event[DynamicData]) -> None:
    data = event.data
    print(data.author.name, data.text)
    if data.video is not None:
        print(data.video.title, data.video.jump_url)


@app.subscribe(danmaku_source.uuid, DanmakuType.GIFT)
async def on_gift(event: Event[DanmakuGiftData]) -> None:
    print(event.data.uname, event.data.gift_name, event.data.gift_num)
```

### Bilibili API 调用

`BilibiliApi` 是查询封装，不负责 Source 生命周期。通过与 Source 相同的
`config_key` 获取：

```python
api = app.get_api(BilibiliApi, "bili_account")

latest = await api.get_new_dynamic(uid=123456)
dynamics = await api.get_all_dynamic(uid=123456)
room = await api.get_room_info(room_id=123456)

print(latest.dynamic_id, room.room_info.title)
```

| 方法 | 返回值 | 说明 |
| --- | --- | --- |
| `get_all_dynamic(uid, offset="")` | `list[DynamicData]` | 获取一页动态并转换为领域模型 |
| `get_new_dynamic(uid)` | `DynamicData` | 获取指定用户的最新动态 |
| `get_new_dynamic_list()` | `list[DynamicData]` | 获取当前凭证账号的动态流，要求凭证 |
| `get_room_info(room_id)` | `LiveRoomData` | 获取直播间、主播、观看榜和公告信息 |
| `get_live_danmaku(room_id)` | 上游 `LiveDanmaku` | 创建弹幕连接对象，主要供 Source 使用 |

上游接口错误会原样传播；无数据、凭证缺失或 DTO 转换失败也可能抛 `ValueError`。
应用应在请求边界捕获并记录，避免用空模型掩盖平台字段变化。
