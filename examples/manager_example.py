"""SourceManager 使用示例

1. 创建 BotApp
2. 注册事件源和订阅者
3. 管理生命周期
"""

from logging import getLogger

from butter_bot.app import BotApp, Event
from butter_bot.sources.bilibili import (
    BiliDynamicSource,
    BiliLiveSource,
    DynamicType,
    LiveType,
)
from butter_bot.sources.bilibili.data import DynamicData, LiveRoomData
from butter_bot.utils import setup_logging

setup_logging("DEBUG")
_log = getLogger("BILIBILI")


# ============ 配置 ============ #
#
# 请先在仓库根目录运行以下命令，再填入你的配置:
#   cp examples/config.example.yaml config.yaml
#   bilibili:
#     sessdata: ""
#     bili_jct: ""
#     buvid3: ""
#
# BotApp 会自动读取 config.yaml，无需手动创建 RuntimeConfig。

# 创建 BotApp（自动加载 config.yaml）
app = BotApp()

# ============ 创建事件源 ============ #
# 注册事件源，无需保存返回值
app.add_source(
    source_cls=BiliDynamicSource, watch_targets=[1802011210], poll_interval=100
)
app.add_source(source_cls=BiliLiveSource, watch_targets=[22758221], poll_interval=100)
# 通过类型获取事件源的 UUID（单一实例时无需传 config_key）
dynamic_source = app.get_source(BiliDynamicSource)
assert dynamic_source is not None
dynamic_id = dynamic_source.uuid
live_source = app.get_source(BiliLiveSource)
assert live_source is not None
live_id = live_source.uuid


# ============ 订阅事件 ============ #


@app.subscribe(dynamic_id, DynamicType.ALL)
async def handle_get_dynamic(event: Event[DynamicData]):
    """每次轮询获取动态时都会触发"""
    _log.info(f"{event.data.author.name} 的动态状态: {event.status}")


@app.subscribe(dynamic_id, DynamicType.NEW)
async def handle_new_dynamic(event: Event[DynamicData]):
    """仅当检测到新动态时触发"""
    _log.info(f"[新动态] UP主 {event.data.author.name} 发布了新动态！")
    _log.info(event.data)


@app.subscribe(dynamic_id, DynamicType.DELETED)
async def handle_del_dynamic(event: Event[DynamicData]):
    """仅当检测到删除动态时触发"""
    _log.info(
        f"[删除动态] UP主 {event.data.author.name} 删除了动态 {event.data.text}！"
    )


@app.subscribe(live_id, LiveType.ONLINE)
async def handle_live_online(event: Event[LiveRoomData]):
    """直播中时触发"""
    _log.info(f"{event.data.anchor_info.name} 在直播")


@app.subscribe(live_id, LiveType.ALL)
async def handle_live_status(event: Event[LiveRoomData]):
    """所有直播状态变化时都会触发"""
    _log.info(f"[直播状态] {event.data.anchor_info.name} 当前状态: {event.status}")


@app.subscribe(live_id, LiveType.OPEN)
async def handle_live_open(event: Event[LiveRoomData]):
    """开播时触发"""
    name = event.data.anchor_info.name
    title = event.data.room_info.title
    room_id = event.data.room_info.room_id
    _log.info(f"[开播通知] {name} 开播了！{title} https://live.bilibili.com/{room_id}")


@app.subscribe(live_id, LiveType.CLOSE)
async def handle_live_close(event: Event[LiveRoomData]):
    """下播时触发"""
    name = event.data.anchor_info.name
    _log.info(f"[下播通知] {name} 下播了")


app.run()
