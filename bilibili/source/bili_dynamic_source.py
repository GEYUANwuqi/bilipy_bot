from base_cls import BaseSource
from event import Event
from bilibili.api import BilibiliApi
from bilibili.type import DynamicType
from bilibili.data import DynamicData
from utils import DataPair
from typing import Union, Optional
import traceback
import asyncio
from logging import getLogger


_log = getLogger("BiliDynamicSource")


class BiliDynamicSource(BaseSource):
    """B站动态事件源.

    负责轮询B站动态并发布事件。
    """

    def __init__(self,
                 poll_interval: Union[float, int] = 60,
                 watch_targets: Optional[list[int]] = None,
                 config_key: str = "bilibili"):
        """初始化动态事件源.
        Args:
            poll_interval: 轮询间隔时间（秒）
            watch_targets: 监听用户列表
            config_key: 配置键，默认"bilibili"
        """
        super().__init__()
        self.config_key: str = config_key
        self.poll_interval: Union[float, int] = poll_interval
        self._poll_num: int = 0
        self._members_list: list[int] = []
        self._dynamic_data: dict[int, DataPair[DynamicData]] = {}
        self._task: Optional[asyncio.Task] = None
        if watch_targets is not None:
            self.add_members(watch_targets)

    async def start(self) -> None:
        """启动动态监控."""
        if self.running:
            _log.warning("动态监控已在运行中")
            return

        self.running = True
        self._task = asyncio.create_task(self._monitor_loop())
        _log.info("B站动态监控已启动")

    async def stop(self) -> None:
        """停止动态监控."""
        if not self.running:
            _log.warning("动态监控未在运行")
            return

        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        _log.info("B站动态监控已停止")

    def add_members(self, keys: list[int]) -> None:
        """添加监控成员.

        Args:
            keys: 监控成员UID列表
        """
        for uid in keys:
            if uid not in self._members_list:
                self._members_list.append(uid)
                _log.debug(f"添加 UID '{uid}' 到监控列表")
            else:
                _log.warning(f"UID '{uid}' 已存在于监控列表中")

    def remove_members(self, keys: list[int]) -> None:
        """移除监控成员.

        Args:
            keys: 监控成员UID列表
        """
        for uid in keys:
            if uid in self._members_list:
                self._members_list.remove(uid)
                _log.debug(f"从监控列表移除 UID '{uid}'")
            else:
                _log.warning(f"UID '{uid}' 不存在于监控列表中")

    def set_poll_interval(self, interval: Union[float, int]) -> None:
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
        _log.info(f"轮询间隔时间已设置为 {self.poll_interval} 秒")

    @property
    def api(self) -> BilibiliApi:
        """获取 Bilibili API 实例."""
        return self.ctx.api_ctx.get(BilibiliApi, self.config_key)

    @property
    def members(self) -> list[int]:
        """获取监控成员列表."""
        return list(self._members_list)

    @property
    def poll_num(self) -> int:
        """获取已完成的轮询次数."""
        return self._poll_num

    async def _poll_data(self, uid: int) -> Optional[DynamicData]:
        """获取并更新动态数据.

        Args:
            uid: 用户UID

        Returns:
            新获取的动态数据
        """
        try:
            new_data = await self.api.get_new_dynamic(uid)

            if uid not in self._dynamic_data:
                self._dynamic_data[uid] = DataPair()
                _log.info(f"初始化 '{uid}' 的动态数据")

            self._dynamic_data[uid].update(new_data)
            return new_data

        except Exception as e:
            _log.error(f"获取 '{uid}' 动态数据时出错: {e}")
            raise

    def _get_dynamic_status(self, uid: int) -> DynamicType:
        """判断动态状态.

        Args:
            uid: 用户UID

        Returns:
            当前的动态状态
        """
        old_timestamp = self._dynamic_data[uid].old.pub_ts
        new_timestamp = self._dynamic_data[uid].new.pub_ts

        if new_timestamp > old_timestamp:
            return DynamicType.NEW
        elif new_timestamp < old_timestamp:
            return DynamicType.DELETED
        else:
            return DynamicType.NULL

    async def _poll_dynamic(self, uid: int) -> None:
        """轮询单个用户的动态.

        Args:
            uid: 用户UID
        """
        try:
            new_data = await self._poll_data(uid=uid)

            if new_data is None:
                _log.warning(f"获取 {uid} 动态数据失败")
                return

            status = self._get_dynamic_status(uid)

            # 根据状态决定传递哪个数据
            if status == DynamicType.DELETED:
                data = self._dynamic_data[uid].get_data("old")
            else:
                data = new_data

            event = Event(data=data, status=status)
            await self.ctx.bus.publish(self.uuid, event)

        except Exception as e:
            _log.error(f"轮询 UID '{uid}' 动态数据时出错: {e}")
            _log.error(traceback.format_exc())

    async def _monitor_loop(self) -> None:
        """监控主循环."""
        _log.info("动态监控循环已启动")

        try:
            while self.running:
                monitored_uids = list(self._members_list)

                if not monitored_uids:
                    await asyncio.sleep(5)
                    continue

                for uid in monitored_uids:
                    if not self.running:
                        break

                    try:
                        await self._poll_dynamic(uid)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        _log.error(f"轮询 UID '{uid}' 时出错: {e}")

                    if not self.running:
                        break

                    try:
                        await asyncio.sleep(self.poll_interval)
                    except asyncio.CancelledError:
                        raise

                self._poll_num += 1
                _log.debug(f"完成第 {self._poll_num} 轮动态监控")

        except asyncio.CancelledError:
            _log.debug("监控循环被取消")
        except Exception as e:
            _log.error(f"监控循环异常: {e}", exc_info=True)
        finally:
            _log.info("动态监控循环已停止")
