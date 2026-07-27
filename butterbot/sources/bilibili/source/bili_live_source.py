import traceback
from logging import getLogger
from uuid import UUID

from butterbot.core.event import Event
from butterbot.utils import DataPair

from ..api import BilibiliApi
from ..data import LiveRoomData
from ..types import LiveType
from .base_polling_source import BasePollingSource

_log = getLogger("BiliLiveSource")


class BiliLiveSource(BasePollingSource):
    """B站直播事件源.

    负责轮询B站直播状态并发布事件。
    """

    supported_types = LiveType
    source_kind = "bilibili.live"
    config_key = "bilibili"
    _log = _log
    _source_name = "B站直播监控"
    _target_name = "房间"

    def __init__(
        self,
        poll_interval: float | int = 20,
        watch_targets: list[int] | None = None,
        *,
        uuid: UUID | None = None,
        config_key: str | None = None,
    ) -> None:
        """初始化直播事件源.
        Args:
            poll_interval: 轮询间隔时间（秒）
            watch_targets: 监听用户列表
        """
        super().__init__(
            poll_interval,
            watch_targets,
            uuid=uuid,
            config_key=config_key,
        )
        self._live_data: dict[int, DataPair[LiveRoomData]] = {}

    @property
    def api(self) -> BilibiliApi:
        """获取 Bilibili API 实例."""
        return self.ctx.api_ctx.get(BilibiliApi, self.config_key)

    @property
    def rooms(self) -> list[int]:
        """获取监控房间列表."""
        return self.watch_targets

    async def _poll_data(self, room_id: int) -> LiveRoomData | None:
        """获取并更新直播数据.

        Args:
            room_id: 直播间ID

        Returns:
            新获取的直播数据
        """
        try:
            new_data = await self.api.get_room_info(room_id)

            if room_id not in self._live_data:
                self._live_data[room_id] = DataPair()
                _log.info("初始化房间 '%s' 的直播数据", room_id)

            self._live_data[room_id].update(new_data)
            return new_data

        except Exception as e:
            _log.error("获取房间 '%s' 直播数据时出错: %s", room_id, e)
            raise

    async def _poll_live(self, room_id: int) -> None:
        """轮询单个房间的直播状态.

        Args:
            room_id: 直播间ID
        """
        try:
            new_data = await self._poll_data(room_id=room_id)

            if new_data is None:
                _log.warning("获取房间 %s 直播数据失败", room_id)
                return

            status = self._get_live_status(room_id)

            event: Event[LiveRoomData] = Event(data=new_data, status=status)
            await self.ctx.bus.publish(self.uuid, event)

        except Exception as e:
            _log.error("轮询房间 '%s' 直播数据时出错: %s", room_id, e)
            _log.error(traceback.format_exc())

    def _get_live_status(
        self,
        room_id: int,
    ) -> LiveType:
        """判断直播状态.
        Args:
            room_id: 直播间ID

        Returns:
            LiveType: 当前的直播状态
        """
        data_pair = self._live_data[room_id]
        old_data = data_pair.old
        new_data = data_pair.new
        if old_data is None or new_data is None:
            return LiveType.NULL

        old_status = old_data.room_info.live_status
        new_status = new_data.room_info.live_status
        # 刚开播：旧状态不是直播中(0或2)，新状态是直播中(1)
        if old_status != 1 and new_status == 1:
            return LiveType.OPEN
        # 刚下播：旧状态是直播中(1)，新状态不是直播中(0或2)
        elif old_status == 1 and new_status != 1:
            return LiveType.CLOSE
        # 直播中：新旧状态都是直播中(1)
        elif old_status == 1 and new_status == 1:
            return LiveType.ONLINE
        # 未开播：其他情况(包括一直未开播、轮播等状态)
        else:
            return LiveType.OFFLINE

    async def _poll_target(self, target: int) -> None:
        await self._poll_live(target)
