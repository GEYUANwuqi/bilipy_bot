from bilibili_api import Credential

from manager import SourceManager, RuntimeConfig
from bilibili import BiliDanmakuSource, DanmakuType
from event import Event
from bilibili.data import LiveRoomData
from utils import setup_logging
from logging import getLogger
import asyncio


setup_logging("DEBUG")
_log = getLogger("BILIBILI")


# ============ 配置 ============ #

# B站凭证（可选）
credential = Credential(
    sessdata="",
    bili_jct="",
    buvid3=""
)

# 创建运行时配置
config = RuntimeConfig(
    bilibili=credential,
)

# 创建管理器
manager = SourceManager(config)

danmaku_source = manager.add_source(
    source_cls = BiliDanmakuSource,
    room_id = [26498147, 22758221]
)
danmaku_id = danmaku_source.uuid


@manager.subscribe(danmaku_id, DanmakuType.OPEN)
async def handle_live_open(event: Event[LiveRoomData]):
    """开播时触发"""
    name = event.data.anchor_info.name
    title = event.data.room_info.title
    room_id = event.data.room_info.room_id
    _log.info(f"[开播通知] {name} 开播了！{title} https://live.bilibili.com/{room_id}")


async def main():
    _log.info("启动 SourceManager 监控...")
    async with manager:
        _log.info("监控已启动，按 Ctrl+C 停止...")
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            _log.info("收到取消信号")
        finally:
            await manager.close()

    _log.info("监控已停止")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log.info("程序被中断")