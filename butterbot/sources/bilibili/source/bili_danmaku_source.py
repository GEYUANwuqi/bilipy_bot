import asyncio
import concurrent.futures
import inspect
import threading
from logging import DEBUG, INFO, getLogger
from typing import TYPE_CHECKING, Callable, TypeVar
from uuid import UUID

from butterbot.core.data import BaseDataMixin
from butterbot.core.event import Event
from butterbot.core.source import BaseSource

from ..api import BilibiliApi
from ..data import DanmakuGiftData, DanmakuGuardData, DanmakuMsgData
from ..data.dto import DanmakuGiftDTO, DanmakuGuardDTO, DanmakuMsgDTO
from ..types import DanmakuType

if TYPE_CHECKING:
    from bilibili_api.live import LiveDanmaku

_log = getLogger("BiliDanmakuSource")
_EventDataT = TypeVar("_EventDataT", bound=BaseDataMixin)


class _DanmakuRoomWorker:
    """一个房间的受管线程、事件循环与连接任务.

    一房间一线程是为了隔离上游 ``LiveDanmaku`` WebSocket 监听缺陷；
    这里只收拢所有权和跨线程交互，不改变该隔离边界。
    """

    def __init__(
        self,
        room_id: int,
        danmaku: "LiveDanmaku",
        *,
        debug: bool,
        on_failure: Callable[[int, BaseException], None],
    ) -> None:
        self.room_id = room_id
        self.danmaku = danmaku
        self._on_failure = on_failure
        self._state_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connect_task: asyncio.Task[None] | None = None
        self._startup_event = threading.Event()
        self._loop_ready = threading.Event()
        self._closed_event = threading.Event()
        self._ready = False
        self._stop_requested = False
        self._error: BaseException | None = None

        name = "LiveDanmaku(%s)" % room_id
        self.danmaku.logger = getLogger(name)
        self.danmaku.logger.setLevel(DEBUG if debug else INFO)
        self.danmaku.add_event_listener(
            "VERIFICATION_SUCCESSFUL",
            self._on_verified,
        )

    @property
    def thread(self) -> threading.Thread | None:
        return self._thread

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        return self._loop

    @property
    def connect_task(self) -> asyncio.Task[None] | None:
        return self._connect_task

    @property
    def ready(self) -> bool:
        with self._state_lock:
            return self._ready

    @property
    def error(self) -> BaseException | None:
        with self._state_lock:
            return self._error

    @property
    def closed(self) -> bool:
        return self._closed_event.is_set()

    @property
    def stop_requested(self) -> bool:
        with self._state_lock:
            return self._stop_requested

    async def _on_verified(self, _event: dict) -> None:
        with self._state_lock:
            self._ready = True
            self._error = None
        self._startup_event.set()
        _log.info("房间 %s 的弹幕姬已连接", self.room_id)

    async def start(self, timeout: float) -> None:
        """启动独立线程并异步等待认证就绪."""
        thread = self._thread
        if thread is not None and thread.is_alive():
            if self.ready:
                return
            raise RuntimeError("房间 %s 正在启动" % self.room_id)

        with self._state_lock:
            self._ready = False
            self._error = None
            self._stop_requested = False
        self._startup_event.clear()
        self._loop_ready.clear()
        self._closed_event.clear()
        self._loop = None
        self._connect_task = None
        thread = threading.Thread(
            target=self._thread_main,
            name="LiveDanmaku(%s)" % self.room_id,
            daemon=True,
        )
        self._thread = thread
        thread.start()

        started = await asyncio.to_thread(self._startup_event.wait, timeout)
        if not started:
            raise TimeoutError("房间 %s 连接就绪超时" % self.room_id)
        error = self.error
        if error is not None:
            raise RuntimeError("房间 %s 连接失败" % self.room_id) from error
        if not self.ready:
            raise RuntimeError("房间 %s 未进入就绪状态" % self.room_id)

    def _thread_main(self) -> None:
        """线程入口：创建、驱动并最终关闭房间事件循环."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._loop_ready.set()
        connect_task = loop.create_task(self._run_connection())
        connect_task.add_done_callback(self._consume_connect_result)
        self._connect_task = connect_task
        try:
            loop.run_forever()
        finally:
            pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
            loop.close()
            self._closed_event.set()
            self._startup_event.set()

    async def _run_connection(self) -> None:
        """持有并消费上游 connect task 的结果."""
        terminal_error: BaseException | None = None
        try:
            await self.danmaku.connect()
        except asyncio.CancelledError as exc:
            if not self.stop_requested:
                terminal_error = exc
        except BaseException as exc:
            terminal_error = exc
        else:
            if not self.stop_requested:
                reason = getattr(self.danmaku, "err_reason", "")
                terminal_error = RuntimeError(
                    str(reason) or "LiveDanmaku connect task exited"
                )

        if terminal_error is not None:
            was_ready = self.ready
            with self._state_lock:
                self._ready = False
                self._error = terminal_error
            self._startup_event.set()
            if was_ready:
                try:
                    self._on_failure(self.room_id, terminal_error)
                except Exception:
                    _log.exception("房间 %s 失败回调异常", self.room_id)

        if not self.stop_requested:
            asyncio.get_running_loop().call_soon(asyncio.get_running_loop().stop)

    def _consume_connect_result(self, task: asyncio.Task[None]) -> None:
        """无论 wrapper 如何退出都显式消费 task 结果."""
        if task.cancelled():
            return
        try:
            task.result()
        except BaseException as exc:
            _log.error("房间 %s connect task 未处理异常: %s", self.room_id, exc)

    async def stop(self, timeout: float) -> None:
        """在房间 loop 中断开，再由工作线程异步 join."""
        thread = self._thread
        if thread is None:
            return
        with self._state_lock:
            self._stop_requested = True
            self._ready = False

        if thread.is_alive() and not self._loop_ready.is_set():
            await asyncio.to_thread(self._loop_ready.wait, timeout)

        # connect wrapper 已终止时，它会自行请求 loop.stop。先等线程
        # 完成 finally，避免向已停止但尚未 close 的 loop 投递新协程。
        connect_task = self._connect_task
        if thread.is_alive() and connect_task is not None and connect_task.done():
            await asyncio.to_thread(thread.join, timeout)
            if not thread.is_alive():
                return

        loop = self._loop
        cleanup_error: BaseException | None = None
        if thread.is_alive() and loop is not None and not loop.is_closed():
            coroutine = self._disconnect()
            try:
                future = asyncio.run_coroutine_threadsafe(coroutine, loop)
            except BaseException as exc:
                coroutine.close()
                cleanup_error = exc
            else:
                try:
                    await asyncio.wait_for(
                        asyncio.wrap_future(future),
                        timeout=timeout,
                    )
                except BaseException as exc:
                    future.cancel()
                    cleanup_error = exc
            try:
                loop.call_soon_threadsafe(loop.stop)
            except RuntimeError:
                pass

        if thread.is_alive():
            await asyncio.to_thread(thread.join, timeout)
        if thread.is_alive():
            timeout_error = TimeoutError("房间 %s 线程未在超时内退出" % self.room_id)
            if cleanup_error is not None:
                timeout_error.add_note(
                    "断开阶段同时失败: %s: %s"
                    % (type(cleanup_error).__name__, cleanup_error)
                )
            raise timeout_error
        if cleanup_error is not None:
            raise cleanup_error

    async def _disconnect(self) -> None:
        """必须在房间事件循环中执行的断开序列."""
        task = self._connect_task
        established = self.danmaku.get_status() == 2
        if established:
            await self.danmaku.disconnect()
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if not established:
            # 上游 disconnect() 在 CONNECTING/ERROR 状态直接拒绝，却可能已经
            # 创建 WebSocket。取消 connect task 后在 worker 内封装这个兼容性收尾。
            client = getattr(self.danmaku, "_LiveDanmaku__client", None)
            websocket = getattr(self.danmaku, "_LiveDanmaku__ws", None)
            close_websocket = getattr(client, "ws_close", None)
            if websocket is not None and callable(close_websocket):
                close_result = close_websocket(websocket)
                if inspect.isawaitable(close_result):
                    await close_result


class BiliDanmakuSource(BaseSource):
    """B站直播弹幕事件源.

    负责轮询B站直播间弹幕并发布事件。
    """

    supported_types = DanmakuType
    source_kind = "bilibili.danmaku"
    config_key = "bilibili"

    def __init__(
        self,
        room_id: list[int] | None = None,
        debug: bool = False,
        *,
        watch_targets: list[int] | None = None,
        room_ready_timeout: float = 20.0,
        room_stop_timeout: float = 10.0,
        uuid: UUID | None = None,
        config_key: str | None = None,
    ) -> None:
        """初始化B站弹幕源

        Args:
            room_id: 房间号列表（兼容旧参数）
            debug: 是否开启调试
            watch_targets: 房间号列表，与另外两个 Bilibili source 的命名一致
            uuid: 可选事件源 UUID
            config_key: 可选配置键
            room_ready_timeout: 单房间连接认证就绪超时
            room_stop_timeout: 单房间断开和线程退出超时
        """
        if room_id is not None and watch_targets is not None:
            raise TypeError("room_id 与 watch_targets 不能同时提供")
        targets = room_id if room_id is not None else watch_targets
        if targets is None:
            raise TypeError("必须提供 room_id 或 watch_targets")
        if any(
            isinstance(room, bool) or not isinstance(room, int) or room <= 0
            for room in targets
        ):
            raise ValueError("房间号必须是正整数")
        if len(set(targets)) != len(targets):
            raise ValueError("房间号不能重复")
        if room_ready_timeout <= 0 or room_stop_timeout <= 0:
            raise ValueError("房间启停超时必须大于 0")

        super().__init__(uuid=uuid, config_key=config_key)
        self.room_id: list[int] = list(targets)
        self.danmaku_list: dict[int, LiveDanmaku] = {}
        self.debug = debug
        self.room_ready_timeout = room_ready_timeout
        self.room_stop_timeout = room_stop_timeout
        self._workers: dict[int, _DanmakuRoomWorker] = {}
        self._rooms_lock = asyncio.Lock()
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._publish_futures: set[concurrent.futures.Future[None]] = set()
        self._publish_lock = threading.Lock()

    def _create_room(self, room_id: int) -> _DanmakuRoomWorker:
        """创建一个房间对象和受管 worker，但不启动线程."""
        self._validate_room_id(room_id)
        danmaku = self.api.get_live_danmaku(room_id)
        danmaku.add_event_listener("LIVE", self.on_live)
        danmaku.add_event_listener("DANMU_MSG", self.on_danmaku)
        danmaku.add_event_listener("SEND_GIFT", self.on_gift)
        danmaku.add_event_listener("GUARD_BUY", self.on_guard)
        self.danmaku_list[room_id] = danmaku
        worker = _DanmakuRoomWorker(
            room_id,
            danmaku,
            debug=self.debug,
            on_failure=self._room_failed,
        )
        self._workers[room_id] = worker
        return worker

    async def start_room(self, room_id: int) -> None:
        """异步启动已有房间并等待连接就绪."""
        async with self._rooms_lock:
            worker = self._workers.get(room_id)
            if worker is None:
                raise KeyError("房间 %s 不存在" % room_id)
            await worker.start(self.room_ready_timeout)
            self._refresh_room_health()

    async def add_new_room(self, room_id: int) -> None:
        """新建房间并等待独立 worker 就绪."""
        async with self._rooms_lock:
            if room_id in self._workers:
                raise ValueError("房间 %s 已存在" % room_id)
            worker = self._create_room(room_id)
            try:
                await worker.start(self.room_ready_timeout)
            except BaseException as start_error:
                try:
                    await worker.stop(self.room_stop_timeout)
                except BaseException as cleanup_error:
                    if cleanup_error is not start_error:
                        start_error.add_note(
                            "房间 %s 启动回滚失败: %s: %s"
                            % (room_id, type(cleanup_error).__name__, cleanup_error)
                        )
                    self._room_failed(room_id, cleanup_error)
                else:
                    self._workers.pop(room_id, None)
                    self.danmaku_list.pop(room_id, None)
                raise
            self._refresh_room_health()

    async def stop_room(self, room_id: int) -> None:
        """断开房间并等待线程退出，保留对象以便重启."""
        async with self._rooms_lock:
            worker = self._workers.get(room_id)
            if worker is None:
                raise KeyError("房间 %s 不存在" % room_id)
            await worker.stop(self.room_stop_timeout)
            if self.running:
                self._report_degraded(RuntimeError("房间 %s 已停止" % room_id))

    async def remove_room(self, room_id: int) -> None:
        """停止成功后才彻底移除房间所有权."""
        async with self._rooms_lock:
            worker = self._workers.get(room_id)
            if worker is None:
                return
            await worker.stop(self.room_stop_timeout)
            self._workers.pop(room_id, None)
            self.danmaku_list.pop(room_id, None)
            _log.info("房间 %s 的弹幕姬已移除", room_id)
            self._refresh_room_health()

    async def on_start(self) -> None:
        """启动弹幕监控."""
        if not self.ctx.config.get_config(self.config_key):
            raise RuntimeError("未找到Credential配置")
        self._main_loop = asyncio.get_running_loop()
        workers = [self._create_room(rid) for rid in self.room_id]
        start_tasks = [
            asyncio.create_task(worker.start(self.room_ready_timeout))
            for worker in workers
        ]
        try:
            await asyncio.gather(*start_tasks)
        except BaseException:
            for task in start_tasks:
                task.cancel()
            await asyncio.gather(*start_tasks, return_exceptions=True)
            raise
        _log.info("B站弹幕姬已启动")

    async def on_stop(self) -> None:
        """停止所有房间监控."""
        first_error: BaseException | None = None
        for rid in list(self._workers):
            try:
                await self.remove_room(rid)
            except BaseException as exc:
                if first_error is None:
                    first_error = exc
                elif exc is not first_error:
                    first_error.add_note(
                        "房间 %s 后续清理失败: %s: %s" % (rid, type(exc).__name__, exc)
                    )
        await self._cancel_publish_futures()
        self._main_loop = None
        if first_error is not None:
            raise first_error

    def _publish_to_main(self, event: Event[_EventDataT]) -> None:
        """将事件发布调度到主事件循环（线程安全）."""
        if self._main_loop is None:
            _log.error("主事件循环未初始化，无法发布事件")
            raise RuntimeError("主事件循环未初始化")
        coroutine = self.ctx.bus.publish(self.uuid, event)
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, self._main_loop)
        except BaseException:
            coroutine.close()
            raise
        with self._publish_lock:
            self._publish_futures.add(future)
        future.add_done_callback(self._publish_done)

    def _publish_done(self, future: concurrent.futures.Future[None]) -> None:
        """消费跨线程发布结果，避免异常静默丢失."""
        with self._publish_lock:
            self._publish_futures.discard(future)
        if future.cancelled():
            return
        try:
            error = future.exception()
        except BaseException as exc:
            error = exc
        if error is not None:
            _log.error("弹幕事件发布失败: %s", error)
            self._room_failed(-1, error)

    async def _cancel_publish_futures(self) -> None:
        """停止时取消并消费尚未完成的跨线程发布."""
        with self._publish_lock:
            futures = tuple(self._publish_futures)
        for future in futures:
            future.cancel()
        if futures:
            await asyncio.gather(
                *(asyncio.wrap_future(future) for future in futures),
                return_exceptions=True,
            )

    def _room_failed(self, room_id: int, error: BaseException) -> None:
        """从房间线程安全上报运行期故障."""
        loop = self._main_loop
        if loop is None or loop.is_closed() or not self.running:
            return
        loop.call_soon_threadsafe(self._report_degraded, error)
        _log.error("房间 %s worker 已降级: %s", room_id, error)

    def _refresh_room_health(self) -> None:
        """动态增删或重启房间后重新计算 Source 就绪状态."""
        if not self.running:
            return
        if self._workers and all(worker.ready for worker in self._workers.values()):
            self._report_ready()
            return
        self._report_degraded(RuntimeError("存在未就绪的弹幕房间"))

    @staticmethod
    def _validate_room_id(room_id: int) -> None:
        if isinstance(room_id, bool) or not isinstance(room_id, int) or room_id <= 0:
            raise ValueError("房间号必须是正整数")

    @property
    def api(self) -> BilibiliApi:
        """获取 Bilibili API 实例."""
        return self.ctx.api_ctx.get(BilibiliApi, self.config_key)

    async def on_live(self, msg: dict) -> None:
        # 开播事件
        if not msg.get("data", {}).get("live_time", 0):
            # data.live_time不存在时不认为是开播事件
            _log.debug("跳过不存在live_time字段的LIVE事件")
            return
        raw_room_id = msg.get("room_display_id")
        if raw_room_id is None:
            _log.warning("消息中缺少 room_display_id，跳过开播事件")
            return
        room_id = int(raw_room_id)
        info = await self.api.get_room_info(room_id)
        event = Event(data=info, status=DanmakuType.OPEN)
        self._publish_to_main(event)

    async def on_danmaku(self, msg: dict) -> None:
        # 弹幕事件
        dto_data = DanmakuMsgDTO.from_raw(msg)
        if dto_data is not None:
            danmaku_data = DanmakuMsgData.from_dto(dto_data)
            event = Event(data=danmaku_data, status=DanmakuType.DANMAKU)
            self._publish_to_main(event)

    async def on_gift(self, msg: dict) -> None:
        # 礼物事件
        dto_data = DanmakuGiftDTO.from_raw(msg)
        if dto_data is not None:
            danmaku_data = DanmakuGiftData.from_dto(dto_data)
            event = Event(data=danmaku_data, status=DanmakuType.GIFT)
            self._publish_to_main(event)

    async def on_guard(self, msg: dict) -> None:
        # 上舰事件
        dto_data = DanmakuGuardDTO.from_raw(msg)
        if dto_data is not None:
            danmaku_data = DanmakuGuardData.from_dto(dto_data)
            event = Event(data=danmaku_data, status=DanmakuType.GUARD)
            self._publish_to_main(event)
