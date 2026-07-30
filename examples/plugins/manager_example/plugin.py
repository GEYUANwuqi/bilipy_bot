"""Bilibili SourceManager 示例的本地目录插件版本."""

from logging import getLogger

from butterbot.plugin import (
    Event,
    LocalPlugin,
    PluginRegistrar,
    SourceRef,
    SubscriptionSpec,
)
from butterbot.sources.bilibili import DynamicType, LiveType
from butterbot.sources.bilibili.data import DynamicData, LiveRoomData

_log = getLogger("BILIBILI")


async def handle_get_dynamic(event: Event[DynamicData]) -> None:
    """每次轮询获取动态时都会触发."""
    _log.info("%s 的动态状态: %s", event.data.author.name, event.status)


async def handle_new_dynamic(event: Event[DynamicData]) -> None:
    """仅当检测到新动态时触发."""
    _log.info("[新动态] UP主 %s 发布了新动态！", event.data.author.name)
    _log.info("%s", event.data)


async def handle_del_dynamic(event: Event[DynamicData]) -> None:
    """仅当检测到删除动态时触发."""
    _log.info(
        "[删除动态] UP主 %s 删除了动态 %s！",
        event.data.author.name,
        event.data.text,
    )


async def handle_live_online(event: Event[LiveRoomData]) -> None:
    """直播中时触发."""
    _log.info("%s 在直播", event.data.anchor_info.name)


async def handle_live_status(event: Event[LiveRoomData]) -> None:
    """所有直播状态变化时都会触发."""
    _log.info(
        "[直播状态] %s 当前状态: %s",
        event.data.anchor_info.name,
        event.status,
    )


async def handle_live_open(event: Event[LiveRoomData]) -> None:
    """开播时触发."""
    room = event.data.room_info
    _log.info(
        "[开播通知] %s 开播了！%s https://live.bilibili.com/%s",
        event.data.anchor_info.name,
        room.title,
        room.room_id,
    )


async def handle_live_close(event: Event[LiveRoomData]) -> None:
    """下播时触发."""
    _log.info("[下播通知] %s 下播了", event.data.anchor_info.name)


class BilibiliManagerPlugin(LocalPlugin):
    """为配置创建的 Bilibili 动态和直播 Source 注册 Handler."""

    async def register(self, registrar: PluginRegistrar) -> None:
        config_key = str(registrar.settings.get("config_key", "bili_account"))
        dynamic_source = SourceRef("bilibili.dynamic", config_key)
        live_source = SourceRef("bilibili.live", config_key)

        for status, callback in (
            (DynamicType.ALL, handle_get_dynamic),
            (DynamicType.NEW, handle_new_dynamic),
            (DynamicType.DELETED, handle_del_dynamic),
        ):
            registrar.add_subscription(
                SubscriptionSpec(
                    source=dynamic_source,
                    status=status,
                    callback=callback,
                )
            )

        for status, callback in (
            (LiveType.ONLINE, handle_live_online),
            (LiveType.ALL, handle_live_status),
            (LiveType.OPEN, handle_live_open),
            (LiveType.CLOSE, handle_live_close),
        ):
            registrar.add_subscription(
                SubscriptionSpec(
                    source=live_source,
                    status=status,
                    callback=callback,
                )
            )
