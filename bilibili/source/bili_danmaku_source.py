import asyncio
from logging import getLogger, DEBUG, INFO
import threading
from typing import TYPE_CHECKING

from base_cls import BaseSource
from event import Event
from bilibili import BilibiliApi, DanmakuType
from bilibili.data import (
    DanmakuMsgData,
    DanmakuGiftData,
    DanmakuGuardData
)
from bilibili.data.dto import (
    DanmakuMsgDTO,
    DanmakuGiftDTO,
    DanmakuGuardDTO
)

if TYPE_CHECKING:
    from bilibili_api.live import LiveDanmaku

_log = getLogger("BiliDanmakuSource")


class BiliDanmakuSource(BaseSource):

    def __init__(self, room_id: list[int], debug: bool = False, config_key: str = "bilibili"):
        """初始化B站弹幕源
        Args:
            room_id: 房间号列表
            debug: 是否开启调试
            config_key: 配置键，默认"bilibili"
        """
        super().__init__()
        self.config_key: str = config_key
        self.room_id: list[int] = room_id
        self.danmaku_list: dict[int, "LiveDanmaku"] = {}
        self.debug = debug
        self._loops: dict[int, asyncio.AbstractEventLoop] = {}
        self._threads: dict[int, threading.Thread] = {}
        self._main_loop: asyncio.AbstractEventLoop | None = None  # 主事件循环引用

    def _run_room_thread(self, room_id: int, danmaku: "LiveDanmaku", ready: threading.Event) -> None:
        """线程入口：为该房间创建独立事件循环，以 task 方式运行弹幕连接，loop.run_forever() 驱动。"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self._loops[room_id] = loop

        async def _connect():
            @danmaku.on("VERIFICATION_SUCCESSFUL")
            async def _on_connected(_):
                ready.set()
                if danmaku.get_status() == 2:
                    _log.info(f"房间 {room_id} 的弹幕姬已连接")
            try:
                asyncio.get_event_loop().create_task(danmaku.connect())
                _log.debug("等待房间 %d 的弹幕姬连接成功...", room_id)
            except Exception as e:
                _log.error(f"房间 {room_id} 弹幕姬异常退出: {e}")
            finally:
                ready.set()  # 防止异常时 ready 永远不被 set
        loop.create_task(_connect())
        loop.run_forever()

    def _start_room_thread(self, room_id: int, danmaku: "LiveDanmaku") -> None:
        """为已有的 danmaku 对象启动独立线程并等待连接建立."""
        if room_id in self._threads and self._threads[room_id].is_alive():
            _log.warning(f"房间 {room_id} 的弹幕姬已在运行中")
            return
        name = f"LiveDanmaku({room_id})"
        danmaku.logger = getLogger(name)
        danmaku.logger.setLevel(DEBUG if self.debug else INFO)
        ready = threading.Event()
        t = threading.Thread(
            target=self._run_room_thread,
            args=(room_id, danmaku, ready),
            name=name,
            daemon=True,
        )
        self._threads[room_id] = t
        _log.debug(f"正在为房间 {room_id} 启动弹幕姬线程...")
        t.start()

    def start_room(self, room_id: int) -> None:
        """启动已有的房间监控（stop_room 后可重新启动）."""
        danmaku = self.danmaku_list.get(room_id)
        if danmaku is None:
            _log.warning(f"房间 {room_id} 不存在，请先调用 add_new_room")
            return
        self._start_room_thread(room_id, danmaku)

    def add_new_room(self, room_id: int) -> None:
        """新建房间监控并在独立线程中启动."""
        if room_id in self.danmaku_list:
            _log.warning(f"房间 {room_id} 已存在，如需重启请调用 start_room")
            return
        danmaku = self.api.get_live_danmaku(room_id)
        danmaku.add_event_listener("LIVE", self.on_live)
        danmaku.add_event_listener("DANMU_MSG", self.on_danmaku)
        danmaku.add_event_listener("SEND_GIFT", self.on_gift)
        danmaku.add_event_listener("GUARD_BUY", self.on_guard)
        self.danmaku_list[room_id] = danmaku
        _log.debug(f"新建了房间 {room_id} 的弹幕姬对象，正在启动线程...")
        self._start_room_thread(room_id, danmaku)

    def stop_room(self, room_id: int) -> None:
        """断开房间连接并等待线程真正退出（保留 danmaku 对象，可通过 start_room 重启）."""
        danmaku = self.danmaku_list.get(room_id)
        loop = self._loops.get(room_id)
        if danmaku is None or loop is None:
            _log.warning(f"未找到房间 {room_id} 的弹幕姬或其事件循环")
            return
        # 先在房间线程的事件循环中调用 disconnect，等待其完成
        future = asyncio.run_coroutine_threadsafe(danmaku.disconnect(), loop)
        try:
            future.result(timeout=10)
        except Exception as e:
            _log.error(f"停止房间 {room_id} 时出错: {e}")
        # disconnect 完成后，通知 loop.run_forever() 退出，线程自然结束
        loop.call_soon_threadsafe(loop.stop)
        # 等待线程真正退出，确保连接已完全断开
        t = self._threads.get(room_id)
        if t and t.is_alive():
            t.join(timeout=15)
            if t.is_alive():
                _log.warning(f"房间 {room_id} 的线程未能在超时内退出，连接可能未完全断开")
            else:
                _log.info(f"房间 {room_id} 的弹幕姬已暂停")
        self._threads.pop(room_id, None)

    def remove_room(self, room_id: int) -> None:
        """停止并彻底移除房间监控（同时清理 danmaku 对象）."""
        self.stop_room(room_id)  # 断开连接并等待线程退出
        self.danmaku_list.pop(room_id, None)
        _log.info(f"房间 {room_id} 的弹幕姬已移除")

    async def start(self) -> None:
        """启动弹幕监控."""
        if not self.ctx.config.get_config(self.config_key):
            raise RuntimeError("未找到Credential配置")
        if self.running:
            _log.warning("B站弹幕姬已在运行中")
            return
        self._main_loop = asyncio.get_running_loop()  # 保存主事件循环
        self.running = True
        for rid in self.room_id:
            self.add_new_room(rid)
        _log.info("B站弹幕姬已启动")

    async def stop(self) -> None:
        """停止所有房间监控."""
        if not self.running:
            _log.warning("B站弹幕姬未在运行")
            return
        self.running = False
        for rid in list(self._threads.keys()):
            self.remove_room(rid)

    def _publish_to_main(self, event: Event) -> None:
        """将事件发布调度到主事件循环（线程安全）."""
        if self._main_loop is None:
            _log.error("主事件循环未初始化，无法发布事件")
            raise RuntimeError("主事件循环未初始化")
        asyncio.run_coroutine_threadsafe(
            self.ctx.bus.publish(self.uuid, event),
            self._main_loop
        )

    @property
    def api(self) -> BilibiliApi:
        """获取 Bilibili API 实例."""
        return self.ctx.api_ctx.get(BilibiliApi, self.config_key)

    async def on_live(self, msg: dict) -> None:
        # 开播事件
        if not msg.get("data", {}).get("live_time", 0):
            # data.live_time不存在时不认为是开播事件
            _log.debug(f"跳过不存在live_time字段的LIVE事件")
            return
        room_id = msg.get("room_display_id")
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
            event = Event(data = danmaku_data, status = DanmakuType.GUARD)
            self._publish_to_main(event)
