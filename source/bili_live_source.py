from .base_source import BaseSource
from event import Event
from api import BilibiliApi
from bili_data import DataPair, LiveRoomData, get_live_status
from typing import Union, Optional
import traceback
import asyncio
from logging import getLogger


_log = getLogger("BiliLiveSource")


class BiliLiveSource(BaseSource):
    """B站直播事件源.

    负责轮询B站直播状态并发布事件。
    """

    def __init__(self, poll_interval: Union[float, int] = 20):
        """初始化直播事件源.

        Args:
            poll_interval: 轮询间隔时间（秒）
        """
        super().__init__()
        self.poll_interval: Union[float, int] = poll_interval
        self._poll_num: int = 0
        self._room_list: list[int] = []
        self._live_data: dict[int, DataPair[LiveRoomData]] = {}
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """启动直播监控."""
        if self.running:
            _log.warning("直播监控已在运行中")
            return

        self.running = True
        self._task = asyncio.create_task(self._monitor_loop())
        _log.info("B站直播监控已启动")

    async def stop(self) -> None:
        """停止直播监控."""
        if not self.running:
            _log.warning("直播监控未在运行")
            return

        self.running = False
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
                _log.debug(f"添加房间 '{room_id}' 到监控列表")
            else:
                _log.warning(f"房间 '{room_id}' 已存在于监控列表中")

    def remove_members(self, keys: list[int]) -> None:
        """移除监控房间.

        Args:
            keys: 监控房间ID列表
        """
        for room_id in keys:
            if room_id in self._room_list:
                self._room_list.remove(room_id)
                _log.debug(f"从监控列表移除房间 '{room_id}'")
            else:
                _log.warning(f"房间 '{room_id}' 不存在于监控列表中")

    def set_poll_interval(self, interval: Union[float, int]) -> None:
        """设置轮询间隔时间.

        Args:
            interval: 轮询间隔时间（秒）
        """
        if interval <= 0:
            _log.error("非法参数，轮询间隔时间不可小于0")
            return
        elif interval <= 8:
            _log.warning("将轮询间隔时间设置为8s以下，可能导致请求频率过高")
        self.poll_interval = interval
        _log.info(f"轮询间隔时间已设置为 {self.poll_interval} 秒")

    @property
    def api(self) -> BilibiliApi:
        """获取 Bilibili API 实例."""
        return self.ctx.api_ctx.get(BilibiliApi)

    @property
    def rooms(self) -> list[int]:
        """获取监控房间列表."""
        return list(self._room_list)

    @property
    def poll_num(self) -> int:
        """获取已完成的轮询次数."""
        return self._poll_num

    async def _poll_data(self, room_id: int) -> Optional[LiveRoomData]:
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
                _log.info(f"初始化房间 '{room_id}' 的直播数据")

            self._live_data[room_id].update(new_data)
            return new_data

        except Exception as e:
            _log.error(f"获取房间 '{room_id}' 直播数据时出错: {e}")
            raise

    async def _poll_live(self, room_id: int) -> None:
        """轮询单个房间的直播状态.

        Args:
            room_id: 直播间ID
        """
        try:
            new_data = await self._poll_data(room_id=room_id)

            if new_data is None:
                _log.warning(f"获取房间 {room_id} 直播数据失败")
                return

            data_pair = self._live_data[room_id]
            status = get_live_status(data_pair)

            event = Event(data=new_data, status=status)
            await self.ctx.bus.publish(self.uuid, event)

        except Exception as e:
            _log.error(f"轮询房间 '{room_id}' 直播数据时出错: {e}")
            _log.error(traceback.format_exc())

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
                        _log.error(f"轮询房间 '{room_id}' 时出错: {e}")

                    if not self.running:
                        break

                    try:
                        await asyncio.sleep(self.poll_interval)
                    except asyncio.CancelledError:
                        raise

                self._poll_num += 1
                _log.debug(f"完成第 {self._poll_num} 轮直播监控")

        except asyncio.CancelledError:
            _log.debug("监控循环被取消")
        except Exception as e:
            _log.error(f"监控循环异常: {e}", exc_info=True)
        finally:
            _log.info("直播监控循环已停止")
