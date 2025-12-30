from api import BilibiliApi
from event import (
    LiveData, DynamicData, BaseDataT, DataPair,
    get_dynamic_status, get_live_status,
    Event, EventBus
)
from utils import LiveType, DynamicType
from logging import getLogger
from typing import Callable, Optional, Coroutine, Iterable, Any
import asyncio
import threading
import traceback


_log = getLogger(__name__)


class BiliManager:
    """BiliManager类，管理Bilibili相关功能."""

    def __init__(self, sessdata: str = "", poll_interval: int = 20):
        """初始化BiliManager.

        Args:
            sessdata (str): B站登录凭证
            poll_interval (int): 轮询间隔（秒）
        """
        self.api = BilibiliApi(sessdata=sessdata)
        self._poll_interval = poll_interval

        # 使用 DataPair 存储新旧数据
        self._dynamic_data: dict[int, DataPair[DynamicData]] = {}
        self._live_data: dict[int, DataPair[LiveData]] = {}

        # 使用统一的 EventBus 管理事件订阅和发布
        # 通过 status 的类型（LiveType/DynamicType）区分不同的事件类别
        self._event_bus: EventBus = EventBus()

        # 线程和事件循环
        self._monitor_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False

    # 注册器方法 #

    def add_dynamic_callback(
        self,
        uid: list[int],
        callback: Callable[[Event], Coroutine[Any, Any, None]],
        status: DynamicType = DynamicType.ALL
    ):
        """直接添加动态回调函数（不使用装饰器）

        Args:
            uid: 用户UID列表
            callback: 回调函数，接收 Event 参数
            status: 状态过滤器，默认为 DynamicType.ALL（匹配所有状态）
        """
        self._event_bus.add_subscriber(uid, callback, status)

    def add_live_callback(
        self,
        room_id: list[int],
        callback: Callable[[Event], Coroutine[Any, Any, None]],
        status: LiveType = LiveType.ALL
    ):
        """直接添加直播回调函数（不使用装饰器）

        Args:
            room_id: 直播间ID列表
            callback: 回调函数，接收 Event 参数
            status: 状态过滤器，默认为 LiveType.ALL（匹配所有状态）
        """
        self._event_bus.add_subscriber(room_id, callback, status)

    # 装饰器方法 #

    def on_dynamic(
        self,
        uid: list[int],
        status: DynamicType = DynamicType.ALL
    ):
        """装饰器：获取动态时回调.

        Args:
            uid (list[int]): 用户UID列表
            status (DynamicType): 指定触发回调的时机
                - DynamicType.ALL: 每次轮询都触发（默认）
                - DynamicType.NEW: 仅在检测到新动态时触发
                - DynamicType.DELETED: 仅在动态被删除时触发
                - DynamicType.NULL: 仅在没有动态时触发

        Usage:
            # 每次轮询都触发（默认）
            @manager.on_dynamic(uid=[123456, 789012])
            async def handle_dynamic(event: Event):
                print(f"获取到动态: {event.data}, 状态: {event.status}")

            # 仅在有新动态时触发
            @manager.on_dynamic(uid=[123456, 789012], status=DynamicType.NEW)
            async def handle_new_dynamic(event: Event):
                print(f"新动态: {event.data}")
        """
        def decorator(
            func: Callable[[Event], Coroutine[Any, Any, None]]
        ):
            self.add_dynamic_callback(uid, func, status)
            return func
        return decorator

    def on_live(
        self,
        room_id: list[int],
        status: LiveType = LiveType.ALL
    ):
        """装饰器：获取直播状态回调.

        Args:
            room_id (list[int]): 直播间ID列表
            status (LiveType): 指定触发回调的状态
                - LiveType.ALL: 所有状态都触发（默认）
                - LiveType.OPEN: 仅在开播时触发
                - LiveType.CLOSE: 仅在下播时触发
                - LiveType.ONLINE: 仅在直播中时触发
                - LiveType.OFFLINE: 仅在未开播时触发

        Usage:
            # 监听所有状态（使用 ALL 通配符）
            @manager.on_live(room_id=[12345, 67890], status=LiveType.ALL)
            async def handle_all_status(event: Event):
                print(f"直播间数据更新: {event.data}, 状态: {event.status}")

            # 仅在开播时触发
            @manager.on_live(room_id=[12345, 67890], status=LiveType.OPEN)
            async def handle_open(event: Event):
                print(f"开播了！")

            # 仅在下播时触发
            @manager.on_live(room_id=[12345, 67890], status=LiveType.CLOSE)
            async def handle_close(event: Event):
                print(f"下播了！")
        """
        def decorator(
            func: Callable[[Event], Coroutine[Any, Any, None]]
        ):
            self.add_live_callback(room_id, func, status)
            return func
        return decorator

    # 轮询处理方法 #

    async def _poll_data(
        self,
        id_key: int,
        fetch_func: Callable,
        data_attr: str
    ) -> BaseDataT:
        """获取并更新数据.

        Args:
            id_key (int): 数据的唯一标识（uid或room_id）
            fetch_func (Callable): 获取数据的异步函数
            data_attr (str): 存储 DataPair 的实例属性名称

        Returns:
            new_data 新数据
        """
        try:
            # 获取新数据
            new_data = await fetch_func()

            # 获取实例属性
            data_dict = getattr(self, data_attr)

            # 初始化或更新数据
            if id_key not in data_dict:
                data_dict[id_key] = DataPair()
                _log.info(f"初始化'{id_key}' 的数据")

            data_dict[id_key].update(new_data)

            return new_data

        except Exception as e:
            _log.error(f"获取 '{id_key}' 数据时出错: {e}")
            raise e

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
            new_data: DynamicData = await self._poll_data(
                id_key=uid,
                fetch_func=lambda: self.api.get_new_dynamic(uid),
                data_attr="_dynamic_data"
            )

            # 获取数据对
            data_pair = self._dynamic_data[uid]

            # 判断状态
            status = get_dynamic_status(data_pair)

            # 根据状态决定传递哪个数据
            if status == DynamicType.DELETED:
                # 动态被删除，获取旧数据
                data = data_pair.get_data("old")
            else:
                # 其他情况，传递新数据
                data = new_data

            # 创建事件并通过 EventBus 发布
            event = Event(data=data, status=status)
            await self._event_bus.publish(uid, event)

        except Exception as e:
            _log.error(f"轮询UID '{uid}' 动态数据时出错: {e}")
            _log.error(traceback.format_exc())

    async def _poll_live(
        self,
        room_id: int
    ):
        """轮询直播数据.

        Args:
            room_id (int): 直播间ID
        """
        try:
            # 使用通用轮询函数获取数据
            new_data: LiveData = await self._poll_data(
                id_key=room_id,
                fetch_func=lambda: self.api.get_room_info(room_id),
                data_attr="_live_data"
            )

            # 获取数据对
            data_pair = self._live_data[room_id]
            # 判断状态
            status = get_live_status(data_pair)

            # 创建事件并通过 EventBus 发布
            event = Event(data=new_data, status=status)
            await self._event_bus.publish(room_id, event)

        except Exception as e:
            _log.error(f"轮询房间 '{room_id}' 直播数据时出错: {e}")
            _log.error(traceback.format_exc())

    # 线程运行方法 #

    # TODO: 捕捉error，或者在logger里写
    async def _run_tasks(
        self,
        task_factories: Iterable[Callable[[], Coroutine]]
    ):
        """全局串行锁式轮询运行任务列表.

        按顺序执行每个任务：执行任务1 -> 等待间隔 -> 执行任务2
        """
        while self._running:
            for factory in task_factories:
                if not self._running:
                    _log.debug("检测到停止信号，退出任务循环")
                    return
                # 执行任务
                try:
                    await factory()
                except asyncio.CancelledError:
                    _log.debug("任务被取消")
                    return
                except Exception as e:
                    _log.error(traceback.format_exc())
                    _log.error(f"执行任务时出错: {e}")

                # 检查是否需要停止
                if not self._running:
                    return

                # 等待间隔时间后再执行下一个任务
                try:
                    await asyncio.sleep(self._poll_interval)
                except asyncio.CancelledError:
                    _log.debug("等待间隔被取消")
                    return

    async def _monitor_loop(self):
        """监控主循环."""

        _log.info("BiliManager 监控循环已启动")

        try:
            # 创建所有轮询任务
            tasks = []
            # 动态轮询（通过 DynamicType 获取监控的 UID）
            monitored_uids = self._event_bus.get_monitored_keys(DynamicType)
            if monitored_uids:
                dynamic_factories = [
                    lambda uid = uid: self._poll_dynamic(uid) for uid in monitored_uids
                ]
                tasks.append(self._run_tasks(dynamic_factories))

            # 直播轮询（通过 LiveType 获取监控的房间 ID）
            monitored_room_ids = self._event_bus.get_monitored_keys(LiveType)
            if monitored_room_ids:
                live_factories = [
                    lambda room_id = room_id: self._poll_live(room_id) for room_id in monitored_room_ids
                ]
                tasks.append(self._run_tasks(live_factories))
            # 并行运行所有任务
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            _log.info("监控循环已被取消")
        except Exception as e:
            _log.error(traceback.format_exc())
            _log.error(f"监控循环执行错误: {e}")

    def _run_monitor_loop(self):
        """在线程中运行异步监控循环."""
        # 创建新的事件循环
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._monitor_loop())
        except Exception as e:
            _log.error(f"事件循环执行错误: {e}")
        finally:
            try:
                # 取消所有待处理的任务
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()

                # 等待所有任务完成取消
                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )

                # 关闭异步生成器
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())

                # 关闭事件循环
                self._loop.close()
                _log.debug("事件循环已正常关闭")
            except Exception as e:
                _log.warning(f"关闭事件循环时出现警告: {e}")

    def start(self):
        """启动监控线程."""
        if self._running:
            _log.warning("监控已经在运行中")
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._run_monitor_loop, daemon=True)
        self._monitor_thread.start()
        _log.info("BiliManager 监控已启动")

    def stop(self):
        """终止监控线程."""
        if not self._running:
            _log.warning("监控未在运行")
            return

        _log.info("正在终止 BiliManager 监控...")
        # 设置停止信号
        self._running = False
        # 如果事件循环存在且正在运行，线程安全地停止它
        if self._loop and self._loop.is_running():
            def cancel_all_tasks():
                for task in asyncio.all_tasks(self._loop):
                    task.cancel()
            self._loop.call_soon_threadsafe(cancel_all_tasks)

        # 等待监控线程结束（最多等待轮询间隔+2秒）
        if self._monitor_thread and self._monitor_thread.is_alive():
            timeout = self._poll_interval + 2
            self._monitor_thread.join(timeout=timeout)
            _log.info("监控线程已正常结束")

        self._monitor_thread = None
        self._loop = None
        _log.info("BiliManager 监控已停止")

    # 属性方法 #

    def set_poll_interval(self, interval: int):
        """设置轮询间隔.

        Args:
            interval (int): 轮询间隔（秒），建议不低于5秒

        Raises:
            ValueError: 当间隔小于1秒时抛出异常
        """
        if interval < 1:
            raise ValueError("轮询间隔不能小于1秒")

        old_interval = self._poll_interval
        self._poll_interval = interval
        _log.info(f"轮询间隔已从 {old_interval} 秒更改为 {interval} 秒")

    @property
    def poll_interval(self) -> int:
        """获取当前轮询间隔.

        Returns:
            int: 当前轮询间隔（秒）
        """
        return self._poll_interval

    @property
    def uids(self) -> list[int]:
        """获取当前监控的UID列表.

        Returns:
            list[int]: 当前监控的UID列表
        """
        return list(self._event_bus.get_monitored_keys(DynamicType))

    @property
    def room_ids(self) -> list[int]:
        """获取当前监控的直播间ID列表.

        Returns:
            list[int]: 当前监控的直播间ID列表
        """
        return list(self._event_bus.get_monitored_keys(LiveType))
