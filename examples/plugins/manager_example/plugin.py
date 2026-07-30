"""Bilibili SourceManager 示例的本地目录插件版本."""

from logging import getLogger

from butterbot.plugin import (
    ButterPlugin,
    Event,
    PluginRegistrar,
    SourceRef,
    SubscriptionSpec,
)
from butterbot.sources.bilibili import DynamicType, LiveType
from butterbot.sources.bilibili.data import DynamicData, LiveRoomData

_log = getLogger("BILIBILI")


class BilibiliManagerPlugin(ButterPlugin):
    """为配置创建的 Bilibili 动态和直播 Source 注册 Handler."""

    async def on_start(self) -> None:
        """全部 Bilibili Source 启动后执行."""
        _log.info("Bilibili Manager 插件已启动")

    async def on_stop(self) -> None:
        """停止 Source 和撤销 Handler 前执行."""
        _log.info("Bilibili Manager 插件正在停止")

    async def register(self, registrar: PluginRegistrar) -> None:
        config_key = str(registrar.settings.get("config_key", "bili_account"))
        dynamic_source = SourceRef("bilibili.dynamic", config_key)
        live_source = SourceRef("bilibili.live", config_key)

        for status, callback in (
            (DynamicType.ALL, self.handle_get_dynamic),
            (DynamicType.NEW, self.handle_new_dynamic),
            (DynamicType.DELETED, self.handle_del_dynamic),
        ):
            registrar.add_subscription(
                SubscriptionSpec(
                    source=dynamic_source,
                    status=status,
                    callback=callback,
                )
            )

        for status, callback in (
            (LiveType.ONLINE, self.handle_live_online),
            (LiveType.ALL, self.handle_live_status),
            (LiveType.OPEN, self.handle_live_open),
            (LiveType.CLOSE, self.handle_live_close),
        ):
            registrar.add_subscription(
                SubscriptionSpec(
                    source=live_source,
                    status=status,
                    callback=callback,
                )
            )

    async def handle_get_dynamic(self, event: Event[DynamicData]) -> None:
        """每次轮询获取动态时都会触发."""
        _log.info("%s 的动态状态: %s", event.data.author.name, event.status)

    async def handle_new_dynamic(self, event: Event[DynamicData]) -> None:
        """仅当检测到新动态时触发."""
        _log.info("[新动态] UP主 %s 发布了新动态！", event.data.author.name)
        _log.info("%s", event.data)

    async def handle_del_dynamic(self, event: Event[DynamicData]) -> None:
        """仅当检测到删除动态时触发."""
        _log.info(
            "[删除动态] UP主 %s 删除了动态 %s！",
            event.data.author.name,
            event.data.text,
        )

    async def handle_live_online(self, event: Event[LiveRoomData]) -> None:
        """直播中时触发."""
        _log.info("%s 在直播", event.data.anchor_info.name)

    async def handle_live_status(self, event: Event[LiveRoomData]) -> None:
        """所有直播状态变化时都会触发."""
        _log.info(
            "[直播状态] %s 当前状态: %s",
            event.data.anchor_info.name,
            event.status,
        )

    async def handle_live_open(self, event: Event[LiveRoomData]) -> None:
        """开播时触发."""
        room = event.data.room_info
        _log.info(
            "[开播通知] %s 开播了！%s https://live.bilibili.com/%s",
            event.data.anchor_info.name,
            room.title,
            room.room_id,
        )

    async def handle_live_close(self, event: Event[LiveRoomData]) -> None:
        """下播时触发."""
        _log.info("[下播通知] %s 下播了", event.data.anchor_info.name)
