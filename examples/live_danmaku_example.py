"""B站直播弹幕使用示例

1. 创建 BotApp
2. 注册弹幕事件源和订阅者
3. 管理生命周期
"""

from logging import getLogger

from bilipy_bot.app import BotApp, Event
from bilipy_bot.sources.bilibili import BiliDanmakuSource, DanmakuType
from bilipy_bot.sources.bilibili.data import LiveRoomData
from bilipy_bot.utils import setup_logging

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

app.add_source(source_cls=BiliDanmakuSource, room_id=[26498147, 22758221])
source = app.get_source(BiliDanmakuSource)
assert source is not None
danmaku_id = source.uuid


@app.subscribe(danmaku_id, DanmakuType.OPEN)
async def handle_live_open(event: Event[LiveRoomData]):
    """开播时触发"""
    name = event.data.anchor_info.name
    title = event.data.room_info.title
    room_id = event.data.room_info.room_id
    _log.info(f"[开播通知] {name} 开播了！{title} https://live.bilibili.com/{room_id}")


app.run()
