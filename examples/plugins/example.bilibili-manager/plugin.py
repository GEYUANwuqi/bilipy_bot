"""Bilibili SourceManager 示例的本地目录插件版本."""

from logging import getLogger

from butterbot.core import Event
from butterbot.plugin import ButterPlugin, register
from butterbot.sources.bilibili import DynamicType, LiveType
from butterbot.sources.bilibili.data import DynamicData, LiveRoomData

_log = getLogger("BILIBILI")


class BilibiliManagerPlugin(ButterPlugin):
    """为配置创建的 Bilibili 动态和直播 Source 注册 Handler."""

    @register("bilibili.dynamic", DynamicType.ALL)
    async def handle_get_dynamic(self, event: Event[DynamicData]) -> None:
        """每次轮询获取动态时都会触发."""
        _log.info("%s 的动态状态: %s", event.data.author.name, event.status)

    @register("bilibili.dynamic", DynamicType.NEW)
    async def handle_new_dynamic(self, event: Event[DynamicData]) -> None:
        """仅当检测到新动态时触发."""
        _log.info("[新动态] UP主 %s 发布了新动态！", event.data.author.name)
        _log.info("%s", event.data)

    @register("bilibili.dynamic", DynamicType.DELETED)
    async def handle_del_dynamic(self, event: Event[DynamicData]) -> None:
        """仅当检测到删除动态时触发."""
        _log.info(
            "[删除动态] UP主 %s 删除了动态 %s！",
            event.data.author.name,
            event.data.text,
        )

    @register("bilibili.live", LiveType.ONLINE)
    async def handle_live_online(self, event: Event[LiveRoomData]) -> None:
        """直播中时触发."""
        _log.info("%s 在直播", event.data.anchor_info.name)

    @register("bilibili.live", LiveType.ALL)
    async def handle_live_status(self, event: Event[LiveRoomData]) -> None:
        """所有直播状态变化时都会触发."""
        _log.info(
            "[直播状态] %s 当前状态: %s",
            event.data.anchor_info.name,
            event.status,
        )

    @register("bilibili.live", LiveType.OPEN)
    async def handle_live_open(self, event: Event[LiveRoomData]) -> None:
        """开播时触发."""
        room = event.data.room_info
        _log.info(
            "[开播通知] %s 开播了！%s https://live.bilibili.com/%s",
            event.data.anchor_info.name,
            room.title,
            room.room_id,
        )

    @register("bilibili.live", LiveType.CLOSE)
    async def handle_live_close(self, event: Event[LiveRoomData]) -> None:
        """下播时触发."""
        _log.info("[下播通知] %s 下播了", event.data.anchor_info.name)
