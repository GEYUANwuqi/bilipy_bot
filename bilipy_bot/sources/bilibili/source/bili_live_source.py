import asyncio
import traceback
from logging import getLogger

from bilipy_bot.core.event import Event
from bilipy_bot.core.source import BaseSource
from bilipy_bot.utils import DataPair

from ..api import BilibiliApi
from ..data import LiveRoomData
from ..types import LiveType

_log = getLogger("BiliLiveSource")


class BiliLiveSource(BaseSource):
    """B站直播事件源.

    负责轮询B站直播状态并发布事件。
    """

    supported_types = LiveType
    config_key = "bilibili"

    def __init__(
        self,
        poll_interval: float | int = 20,
        watch_targets: list[int] | None = None,
        **kwargs,
    ):
        """初始化直播事件源.
        Args:
            poll_interval: 轮询间隔时间（秒）
            watch_targets: 监听用户列表
        """
        super().__init__(**kwargs)
        self.poll_interval: float | int = poll_interval
        self._poll_num: int = 0
        self._room_list: list[int] = []
        self._live_data: dict[int, DataPair[LiveRoomData]] = {}
        self._task: asyncio.Task | None = None
        if watch_targets is not None:
            self.add_members(watch_targets)

    async def on_start(self) -> None:
        """启动直播监控."""
        self._task = asyncio.create_task(self._monitor_loop())
        _log.info("B站直播监控已启动")

    async def on_stop(self) -> None:
        """停止直播监控."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        _log.info("B站直播监控已停止")

    def add_members(self, keys: list[int]) -> None:
        """添加监控房间.

        Args:
            keys: 监控房间ID列表
        """
        for room_id in keys:
            if room_id not in self._room_list:
                self._room_list.append(room_id)
                _log.debug("添加房间 '%s' 到监控列表", room_id)
            else:
                _log.warning("房间 '%s' 已存在于监控列表中", room_id)

    def remove_members(self, keys: list[int]) -> None:
        """移除监控房间.

        Args:
            keys: 监控房间ID列表
        """
        for room_id in keys:
            if room_id in self._room_list:
                self._room_list.remove(room_id)
                _log.debug("从监控列表移除房间 '%s'", room_id)
            else:
                _log.warning("房间 '%s' 不存在于监控列表中", room_id)

    def set_poll_interval(self, interval: float | int) -> None:
        """设置轮询间隔时间.

        Args:
            interval: 轮询间隔时间（秒）
        """
        if interval <= 0:
            _log.error("非法参数，轮询间隔时间不可小于或等于0")
            return
        elif interval <= 30:
            _log.warning("将轮询间隔时间设置为30s及以下，可能导致请求频率过高")
        self.poll_interval = interval
        _log.info("轮询间隔时间已设置为 %s 秒", self.poll_interval)

    @property
    def api(self) -> BilibiliApi:
        """获取 Bilibili API 实例."""
        return self.ctx.api_ctx.get(BilibiliApi, self.config_key)

    @property
    def rooms(self) -> list[int]:
        """获取监控房间列表."""
        return list(self._room_list)

    @property
    def poll_num(self) -> int:
        """获取已完成的轮询次数."""
        return self._poll_num

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

            event = Event(data=new_data, status=status)
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

    async def _monitor_loop(self) -> None:
        """监控主循环."""
        _log.info("直播监控循环已启动")

        try:
            while self.running:
                monitored_rooms = list(self._room_list)

                if not monitored_rooms:
                    await asyncio.sleep(5)
                    continue

                for room_id in monitored_rooms:
                    if not self.running:
                        break

                    try:
                        await self._poll_live(room_id)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        _log.error("轮询房间 '%s' 时出错: %s", room_id, e)

                    if not self.running:
                        break

                    try:
                        await asyncio.sleep(self.poll_interval)
                    except asyncio.CancelledError:
                        raise

                self._poll_num += 1
                _log.debug("完成第 %s 轮直播监控", self._poll_num)

        except asyncio.CancelledError:
            _log.debug("监控循环被取消")
        except Exception as e:
            _log.error("监控循环异常: %s", e, exc_info=True)
        finally:
            _log.info("直播监控循环已停止")
