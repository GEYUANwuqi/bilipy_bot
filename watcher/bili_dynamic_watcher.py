from .base_watcher import BaseWatcher
from event import Event
from api import BilibiliApi
from utils import DynamicType
from bili_data import DataPair, DynamicData
from typing import Callable, Iterable, Coroutine, Union, Optional
import traceback
import asyncio
from logging import getLogger

_log = getLogger("BiliDynamicWatcher")


class BiliDynamicWatcher(BaseWatcher):
    """B站动态监控器"""
    poll_interval: Union[float, int] = 15
    _poll_num: int = 0
    members_list: list = []
    dynamic_data: dict[int, DataPair[DynamicData]] = {}

    def start(self):
        self.running = True
        asyncio.create_task(self._monitor_loop())

    def stop(self):
        self.running = False

    def add_members(self, keys: list):
        """添加监控成员.
        Args:
            keys (list): 监控成员UID列表
        """
        for i in keys:
            if i not in self.members_list:
                self.members_list.append(i)
            else:
                _log.warning(f"UID '{i}' 已存在于监控列表中")

    def remove_members(self, keys: list):
        """移除监控成员.
        Args:
            keys (list): 监控成员UID列表
        """
        for i in keys:
            if i in self.members_list:
                self.members_list.remove(i)
            else:
                _log.warning(f"UID '{i}' 不存在于监控列表中")

    def set_poll_interval(self, interval: Union[float, int]):
        """设置轮询间隔时间.

        Args:
            interval (Union[float, int]): 轮询间隔时间（秒）
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
        return self.api_context.get(BilibiliApi)

    @property
    def members(self) -> list:
        return self.members_list

    @property
    def poll_num(self) -> int:
        return self._poll_num

    async def _poll_data(
        self,
        uid: int,
    ) -> Optional[DynamicData]:
        """获取并更新数据.

        Args:
            uid (int): 用户UID

        Returns:
            new_data 新数据
        """
        try:
            # 获取新数据
            new_data = await self.api.get_new_dynamic(uid)

            # 初始化或更新数据
            if uid not in self.dynamic_data:
                self.dynamic_data[uid] = DataPair()
                _log.info(f"初始化'{uid}' 的数据")

            self.dynamic_data[uid].update(new_data)

            return new_data

        except Exception as e:
            _log.error(f"获取 '{uid}' 动态数据时出错: {e}")
            raise e

    def get_dynamic_status(
        self,
        uid: int
    ) -> DynamicType:
        """判断动态状态.
        Returns:
            DynamicType: 当前的动态状态
        """

        old_timestamp = self.dynamic_data[uid].old.pub_ts
        new_timestamp = self.dynamic_data[uid].new.pub_ts
        # 新动态的时间戳大于旧动态，说明有新动态
        if new_timestamp > old_timestamp:
            return DynamicType.NEW
        # 新动态的时间戳早于旧动态，说明动态被删除
        elif new_timestamp < old_timestamp:
            return DynamicType.DELETED
        # 时间戳相同，没有变化
        else:
            return DynamicType.NULL

    async def _poll_dynamic(
        self,
        uid: int
    ):
        """轮询动态数据.

        Args:
            uid (int): 用户UID
        """
        try:
            # 获取数据
            new_data = await self._poll_data(uid=uid)

            if new_data is None:
                _log.warning(f"获取{uid}动态数据失败")
                return

            # 判断状态
            status = self.get_dynamic_status(uid)

            # 根据状态决定传递哪个数据
            if status == DynamicType.DELETED:
                # 动态被删除，获取旧数据
                data = self.dynamic_data[uid].get_data("old")
            else:
                # 其他情况，传递新数据
                data = new_data

            # 创建事件并通过 EventBus 发布
            event = Event(data=data, status=status)
            await self.publish_event(event)

        except Exception as e:
            _log.error(f"轮询UID '{uid}' 动态数据时出错: {e}")
            _log.error(traceback.format_exc())

    async def _run_tasks(
        self,
        task_factories: Iterable[Callable[[], Coroutine]]
    ):
        """全局串行锁式轮询运行任务列表.

        按顺序执行每个任务：执行任务1 -> 等待间隔 -> 执行任务2
        """
        for factory in task_factories:
            if not self.running:
                _log.debug("检测到停止信号，退出任务循环")
                return
            # 执行任务
            try:
                await factory()
            except asyncio.CancelledError:
                _log.warning("当前任务被取消")
                raise
            except Exception as e:
                _log.error(traceback.format_exc())
                _log.error(f"执行任务时出错: {e}")

            # 检查是否需要停止
            if not self.running:
                return

            # 等待间隔时间后再执行下一个任务
            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                _log.debug("等待间隔被取消")
                raise

    async def _monitor_loop(self):
        """监控主循环."""

        _log.info("BiliManager 监控循环已启动")
        try:
            while self.running:
                # 取一个当前成员快照
                monitored_uids = list(self.members_list)

                if not monitored_uids:
                    # 没有 UID，就等着，5s检查一次
                    await asyncio.sleep(5)
                    continue

                dynamic_factories = [
                    lambda uid = uid: self._poll_dynamic(uid)
                    for uid in monitored_uids
                ]

                try:
                    # 串行限速轮询一轮
                    await self._run_tasks(dynamic_factories)
                    self._poll_num += 1
                    _log.info(f"完成第 {self.poll_num} 轮动态监控")
                except asyncio.CancelledError:
                    _log.debug("监控循环被取消")
                    raise
                except Exception as e:
                    _log.error(f"监控循环异常{e}", exc_info = True)
        except asyncio.CancelledError:
            _log.warning("监控主循环被取消")
        except Exception as e:
            _log.warning(f"监控主循环不正常退出{e}")
        finally:
            _log.info("BiliManager 监控循环已停止")
