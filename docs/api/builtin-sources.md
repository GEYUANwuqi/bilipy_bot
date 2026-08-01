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
async send_group_message(group_id: int, message: list[dict]) -> dict | None
```

`create()` 缺配置抛 `ConfigError`。Handler 必须是协程函数。请求可能抛
`TimeoutError` 或 `CancelledError`。

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
