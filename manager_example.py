"""BiliBiliManager 使用示例

展示如何使用重构后的 BiliBiliManager 架构：
1. 创建 BiliBiliManager 和 Source
2. 注册订阅者
3. 管理生命周期
"""
from bilibili_api import Credential

from manager import BiliBiliManager
from source import BiliDynamicSource, BiliLiveSource
from event import Event
from bili_data import DynamicData, LiveRoomData
from utils import LiveType, DynamicType
from utils import setup_logging
from api.context import RuntimeConfig
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
manager = BiliBiliManager(config)

# ============ 创建事件源 ============ #
# TODO: 用依赖注入重构这里的创建过程
# 动态监控源
dynamic_source = BiliDynamicSource(poll_interval=12)
dynamic_source.add_members([1802011210])

# 直播监控源
live_source = BiliLiveSource(poll_interval=12)
live_source.add_members([22758221])

# 注册事件源并获取 UUID
dynamic_id = manager.add_source(dynamic_source)
live_id = manager.add_source(live_source)


# ============ 订阅事件 ============ #

@manager.subscribe(dynamic_id, DynamicType.ALL)
async def handle_get_dynamic(event: Event[DynamicData]):
    """每次轮询获取动态时都会触发"""
    _log.info(f"{event.data.author.name} 的动态状态: {event.status}")


@manager.subscribe(dynamic_id, DynamicType.NEW)
async def handle_new_dynamic(event: Event[DynamicData]):
    """仅当检测到新动态时触发"""
    _log.info(f"[新动态] UP主 {event.data.author.name} 发布了新动态！")
    _log.info(event.data)


@manager.subscribe(dynamic_id, DynamicType.DELETED)
async def handle_del_dynamic(event: Event[DynamicData]):
    """仅当检测到删除动态时触发"""
    _log.info(f"[删除动态] UP主 {event.data.author.name} 删除了动态 {event.data.text}！")


@manager.subscribe(live_id, LiveType.ONLINE)
async def handle_live_online(event: Event[LiveRoomData]):
    """直播中时触发"""
    _log.info(f"{event.data.anchor_info.name} 在直播")


@manager.subscribe(live_id, LiveType.ALL)
async def handle_live_status(event: Event[LiveRoomData]):
    """所有直播状态变化时都会触发"""
    _log.info(f"[直播状态] {event.data.anchor_info.name} 当前状态: {event.status}")


@manager.subscribe(live_id, LiveType.OPEN)
async def handle_live_open(event: Event[LiveRoomData]):
    """开播时触发"""
    name = event.data.anchor_info.name
    title = event.data.room_info.title
    room_id = event.data.room_info.room_id
    _log.info(f"[开播通知] {name} 开播了！{title} https://live.bilibili.com/{room_id}")


@manager.subscribe(live_id, LiveType.CLOSE)
async def handle_live_close(event: Event[LiveRoomData]):
    """下播时触发"""
    name = event.data.anchor_info.name
    _log.info(f"[下播通知] {name} 下播了")


# ============ 主函数 ============ #

async def main():
    _log.info("启动 BiliBiliManager 监控...")
    _log.info(f"动态监控轮询间隔: {dynamic_source.poll_interval} 秒")
    _log.info(f"直播监控轮询间隔: {live_source.poll_interval} 秒")

    # 使用异步上下文管理器
    async with manager:
        _log.info("监控已启动，按 Ctrl+C 停止...")
        try:
            # 保持运行 300 秒
            await asyncio.sleep(300)
        except asyncio.CancelledError:
            _log.info("收到取消信号")

    _log.info("监控已停止")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log.info("\n程序被中断")
