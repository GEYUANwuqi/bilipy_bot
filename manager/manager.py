from api import BilibiliApi
from event import LiveData, DynamicData, get_live_status, is_new_dynamic
from logging import getLogger
from typing import Callable, Optional, Literal, Coroutine, Iterable, Any
import asyncio
import threading
from functools import wraps
import inspect

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

        # 存储新旧数据的实例属性
        self._dynamic_data_old: dict[int, Optional[DynamicData]] = {}
        self._dynamic_data_new: dict[int, Optional[DynamicData]] = {}
        self._live_data_old: dict[int, Optional[LiveData]] = {}
        self._live_data_new: dict[int, Optional[LiveData]] = {}

        self._on_dynamic_callbacks: dict[int, list[tuple[Callable, str]]] = {}
        self._on_live_callbacks: dict[int, list[tuple[Callable, str]]] = {}

        # 监控的UID和room_id
        self._monitored_uids: set[int] = set()
        self._monitored_room_ids: set[int] = set()

        # 线程和事件循环
        self.monitor_thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False


    # 注册回调函数 #


    def _register_callback(
        self,
        callback_attr: str,
        key: int,
        wrapper: Callable,
        func_name: str,
        status_filter: str,
        monitored_set_attr: str
    ):
        """注册回调函数的通用方法.

        Args:
            callback_attr (str): 回调函数字典的属性名
            key (int): 回调的键（uid或room_id）
            wrapper (Callable): 包装后的回调函数
            func_name (str): 原始函数名称
            status_filter (str): 状态过滤器
            monitored_set_attr (str): 监控集合的属性名
        """
        callback_dict = getattr(self, callback_attr)
        if key not in callback_dict:
            callback_dict[key] = []
        # 存储 (callback, status_filter) 元组
        callback_dict[key].append((wrapper, status_filter))

        # 添加到监控集合
        if monitored_set_attr:
            monitored_set = getattr(self, monitored_set_attr)
            monitored_set.add(key)

        status_desc = f"status='{status_filter}'"
        _log.debug(f"为 '{key}' 注册回调函数 '{func_name}' ({status_desc}, attr={callback_attr})")



    # 装饰器方法 #


    def on_dynamic(self, uid: list[int], status: Literal["all", "new"] = "all"):
        """装饰器：获取动态时回调.

        Args:
            uid (list[int]): 用户UID列表
            status (Literal["all", "new"]):
                指定触发回调的时机
                - "all": 每次轮询都触发（默认）
                - "new": 仅在检测到新动态时触发

        Usage:
            # 每次轮询都触发（默认）
            @manager.on_dynamic(uid=[123456, 789012])
            async def handle_dynamic(data: DynamicData):
                print(f"获取到动态: {data}")

            # 仅在有新动态时触发
            @manager.on_dynamic(uid=[123456, 789012], status="new")
            async def handle_new_dynamic(data: DynamicData):
                print(f"新动态: {data}")
        """
        def decorator(func: Callable[[DynamicData], None]):
            if not inspect.iscoroutinefunction(func):
                raise TypeError(f"回调函数 '{func.__name__}' 必须是协程函数")

            @wraps(func)
            async def wrapper(data: DynamicData):
                return await func(data)

            for u in uid:
                self._register_callback(
                    "_on_dynamic_callbacks",
                    u,
                    wrapper,
                    func.__name__,
                    status,
                    "_monitored_uids"
                )
            return wrapper
        return decorator

    def on_live(self, room_id: list[int], status: Literal["all", "open", "close", "opening", "default"] = "all"):
        """装饰器：获取直播状态回调.

        Args:
            room_id (list[int]): 直播间ID列表
            status (Literal["all", "open", "close", "opening", "default"]):
                指定触发回调的状态
                - "all": 所有状态都触发（默认）
                - "open": 仅在开播时触发
                - "close": 仅在下播时触发
                - "opening": 仅在直播中时触发
                - "default": 仅在未开播时触发

        Usage:
            # 所有状态都触发
            @manager.on_live(room_id=[12345, 67890])
            async def handle_all_status(data: LiveData, status: Literal["open", "close", "opening", "default"]):
                print(f"直播状态: {status}")

            # 仅在开播时触发
            @manager.on_live(room_id=[12345, 67890], status="open")
            async def handle_open(data: LiveData):
                print(f"开播了！")
        """
        def decorator(func: Callable):
            if not inspect.iscoroutinefunction(func):
                raise TypeError(f"回调函数 '{func.__name__}' 必须是协程函数")
            # 验证参数使用的合法性
            sig = inspect.signature(func)
            param_count = len(sig.parameters)
            if (status != "all" and param_count == 2) or (status == "all" and param_count == 1):
                raise TypeError(f"注册'{func.__name__}'时出错: 未指定status参数")

            @wraps(func)
            async def wrapper(data: LiveData, live_status: Literal["open", "close", "opening", "default"]):
                if param_count == 2:
                    # 函数接受两个参数 (data, status)
                    return await func(data, live_status)
                else:
                    # 函数只接受一个参数 (data)
                    return await func(data)

            # 注册回调时传递状态过滤器
            for rid in room_id:
                self._register_callback(
                    "_on_live_callbacks",
                    rid,
                    wrapper,
                    func.__name__,
                    status,
                    "_monitored_room_ids"
                )
            return wrapper
        return decorator


    # 轮询处理方法 #


    async def _poll_data(
        self,
        id_key: int,
        fetch_func: Callable,
        old_data_attr: str,
        new_data_attr: str
    ) -> Any:
        """获取并更新数据.

        Args:
            id_key (int): 数据的唯一标识（uid或room_id）
            fetch_func (Callable): 获取数据的异步函数
            old_data_attr (str): 存储旧数据的实例属性名称
            new_data_attr (str): 存储新数据的实例属性名称

        Returns:
            new_data 新数据
        """
        try:
            # 获取新数据
            new_data = await fetch_func()

            # 获取实例属性
            old_data_dict = getattr(self, old_data_attr)
            new_data_dict = getattr(self, new_data_attr)

            # 初始化数据（首次获取）
            if id_key not in old_data_dict:
                old_data_dict[id_key] = new_data
                new_data_dict[id_key] = new_data
                _log.info(f"初始化'{id_key}' 的数据")
            else:
                # 更新数据
                old_data_dict[id_key] = new_data_dict[id_key]
                new_data_dict[id_key] = new_data

            return new_data

        except Exception as e:
            _log.error(f"获取 '{id_key}' 数据时出错: {e}")
            raise

    async def _trigger_callbacks(
        self,
        callback_attr: str,
        key: int,
        *args,
        filter_value: str = ""
    ):
        """批量调用回调函数

        Args:
            callback_attr (str): 回调函数字典的属性名
            key (int): 回调的键（uid或room_id）
            *args: 传递给回调函数的参数
            filter_value (str): 过滤值，用于匹配带过滤器的回调
                - 回调存储格式为 list[tuple[Callable, str]]
                - 过滤器为 "all" 时所有状态都触发，否则只在状态匹配时触发
        """
        callback_dict = getattr(self, callback_attr)
        if key in callback_dict:
            for item in callback_dict[key]:
                try:
                    callback, status_filter = item
                    # status_filter 为 "all" 表示所有状态都触发
                    # 否则只在状态匹配时触发
                    if status_filter != "all" and status_filter != filter_value:
                        continue
                    asyncio.create_task(callback(*args))
                except Exception as e:
                    _log.error(f"执行回调时出错 (attr={callback_attr}, key={key}): {e}")

    async def _poll_dynamic(self, uid: int):
        """轮询动态数据.

        Args:
            uid (int): 用户UID
        """
        try:
            # 使用通用轮询函数获取数据
            new_data:DynamicData = await self._poll_data(
                id_key=uid,
                fetch_func=lambda: self.api.get_new_dynamic(uid),
                old_data_attr="_dynamic_data_old",
                new_data_attr="_dynamic_data_new"
            )

            # 检查是否有新动态
            has_new = is_new_dynamic(self._dynamic_data_old[uid], new_data)

            # 确定当前状态：有新动态为 "new"，否则为空（仅 "all" 过滤器会触发）
            current_status = "new" if has_new else "all"

            if has_new:
                _log.info(f"检测到UID '{uid}' 有新动态")

            # 触发动态回调（检查状态过滤器）
            await self._trigger_callbacks(
                "_on_dynamic_callbacks", uid, new_data, filter_value=current_status
            )

        except Exception as e:
            import traceback
            _log.error(f"轮询UID '{uid}' 动态数据时出错: {e}")
            _log.error(traceback.format_exc())

    async def _poll_live(self, room_id: int):
        """轮询直播数据.

        Args:
            room_id (int): 直播间ID
        """
        try:
            # 使用通用轮询函数获取数据
            new_data:LiveData = await self._poll_data(
                id_key=room_id,
                fetch_func=lambda: self.api.get_room_info(room_id),
                old_data_attr="_live_data_old",
                new_data_attr="_live_data_new"
            )

            # 获取直播状态
            status = get_live_status(self._live_data_old[room_id], new_data)

            # 触发直播回调（检查状态过滤器）
            await self._trigger_callbacks(
                "_on_live_callbacks", room_id, new_data, status, filter_value=status
            )

        except Exception as e:
            _log.error(f"轮询房间 '{room_id}' 直播数据时出错: {e}")


    # 线程运行方法 #


    async def _run_tasks(self, task_factories: Iterable[Callable[[], Coroutine]]):
        """全局锁式轮询运行任务列表.

        按顺序执行每个任务：执行任务1 -> 等待间隔 -> 执行任务2
        """
        while self._running:
            for factory in task_factories:
                # 执行任务
                await factory()
                # 等待间隔时间后再执行下一个任务
                await asyncio.sleep(self._poll_interval)

    async def _monitor_loop(self):
        """监控主循环."""

        _log.info("BiliManager 监控循环已启动")

        try:
            # 创建所有轮询任务
            tasks = []
            # 动态轮询
            if self._monitored_uids:
                dynamic_factories = [
                    lambda uid = uid: self._poll_dynamic(uid) for uid in self._monitored_uids
                ]
                tasks.append(self._run_tasks(dynamic_factories))

            # 直播轮询
            if self._monitored_room_ids:
                live_factories = [
                    lambda room_id = room_id: self._poll_live(room_id) for room_id in self._monitored_room_ids
                ]
                tasks.append(self._run_tasks(live_factories))
            # 并行运行所有任务
            await asyncio.gather(*tasks)
        except Exception as e:
            _log.error(f"监控循环执行错误: {e}")
            await asyncio.sleep(self._poll_interval)

    def _run_monitor_loop(self):
        """在线程中运行异步监控循环."""
        # 创建新的事件循环
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self._monitor_loop())
        except Exception as e:
            _log.error(f"事件循环执行错误: {e}")
        finally:
            try:
                self.loop.stop()
            except Exception as e:
                _log.warning(f"关闭事件循环时出现警告: {e}")

    async def start(self):
        """启动监控线程."""
        if self._running:
            _log.warning("监控已经在运行中")
            return

        self._running = True
        self.monitor_thread = threading.Thread(target=self._run_monitor_loop, daemon=True)
        self.monitor_thread.start()
        _log.info("BiliManager 监控已启动")

    async def stop(self):
        """停止监控线程."""
        if not self._running:
            _log.warning("监控未在运行")
            return

        _log.info("正在停止 BiliManager 监控...")
        self._running = False
        await self.loop.shutdown_asyncgens()
        self.loop.stop()
        self.loop.close()

        # 等待监控线程结束（最多等待轮询间隔+2秒）
        if self.monitor_thread and self.monitor_thread.is_alive():
            timeout = self._poll_interval + 2
            self.monitor_thread.join(timeout=timeout)

            if self.monitor_thread.is_alive():
                _log.warning(f"监控线程在 {timeout} 秒内未能正常结束")
            else:
                _log.info("监控线程已正常结束")

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
