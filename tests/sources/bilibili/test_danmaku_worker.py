"""弹幕房间受管线程 worker 测试."""

import asyncio
import logging
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any, cast

import pytest

from butterbot.app import RuntimeConfig
from butterbot.core.context import AppContext
from butterbot.core.source import SourceHealthState, SourceState
from butterbot.sources.bilibili.source.bili_danmaku_source import (
    BiliDanmakuSource,
    _DanmakuRoomWorker,
)


class FakeDanmaku:
    """可控首连、断开和运行期退出的上游桩."""

    def __init__(self, mode: str = "ready") -> None:
        self.mode = mode
        self.logger = logging.getLogger("FakeDanmaku")
        self.err_reason = ""
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.connect_thread: threading.Thread | None = None
        self._status = 0
        self._listeners: dict[
            str,
            list[Callable[[dict[str, Any]], Awaitable[None]]],
        ] = {}
        self._closed: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def add_event_listener(
        self,
        event: str,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        self._listeners.setdefault(event, []).append(callback)

    async def connect(self) -> None:
        self.connect_calls += 1
        self.connect_thread = threading.current_thread()
        self._loop = asyncio.get_running_loop()
        self._closed = asyncio.Event()
        if self.mode == "fail":
            raise RuntimeError("上游连接失败")
        if self.mode == "hang":
            await self._closed.wait()
            return
        if self.mode == "no_ready":
            return

        self._status = 2
        for callback in self._listeners.get("VERIFICATION_SUCCESSFUL", []):
            await callback({})
        await self._closed.wait()
        self._status = 4

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        if self.mode == "slow_disconnect":
            # 故意阻塞房间线程，验证主 loop 不被一起阻塞。
            time.sleep(0.1)
        self._status = 4
        assert self._closed is not None
        self._closed.set()

    def get_status(self) -> int:
        return self._status

    def exit_unexpectedly(self, reason: str = "连接中断") -> None:
        self.err_reason = reason
        self._status = 3
        assert self._closed is not None
        assert self._loop is not None
        self._loop.call_soon_threadsafe(self._closed.set)


def _worker(
    room_id: int = 100,
    *,
    mode: str = "ready",
    failures: list[tuple[int, BaseException]] | None = None,
) -> tuple[_DanmakuRoomWorker, FakeDanmaku]:
    danmaku = FakeDanmaku(mode)
    failure_sink = failures if failures is not None else []
    worker = _DanmakuRoomWorker(
        room_id,
        cast(Any, danmaku),
        debug=False,
        on_failure=lambda failed_room, error: failure_sink.append((failed_room, error)),
    )
    return worker, danmaku


class TestDanmakuRoomWorker:
    @pytest.mark.asyncio
    async def test_ready_owns_thread_loop_and_connect_task(self) -> None:
        worker, danmaku = _worker()

        await worker.start(timeout=1.0)

        assert worker.ready
        assert worker.thread is not None and worker.thread.is_alive()
        assert worker.loop is not None
        assert worker.loop is not asyncio.get_running_loop()
        assert worker.connect_task is not None
        assert danmaku.connect_thread is worker.thread

        await worker.stop(timeout=1.0)
        assert worker.closed
        assert worker.thread is not None and not worker.thread.is_alive()
        assert worker.loop is not None and worker.loop.is_closed()

    @pytest.mark.asyncio
    async def test_two_rooms_keep_one_distinct_thread_each(self) -> None:
        first, first_danmaku = _worker(100)
        second, second_danmaku = _worker(200)

        await asyncio.gather(first.start(1.0), second.start(1.0))

        assert first_danmaku.connect_thread is not second_danmaku.connect_thread
        assert first.thread is first_danmaku.connect_thread
        assert second.thread is second_danmaku.connect_thread
        await asyncio.gather(first.stop(1.0), second.stop(1.0))

    @pytest.mark.asyncio
    async def test_start_failure_is_propagated_and_thread_closes(self) -> None:
        worker, _ = _worker(mode="fail")

        with pytest.raises(RuntimeError, match="连接失败") as exc_info:
            await worker.start(timeout=1.0)

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        await worker.stop(timeout=1.0)
        assert worker.closed

    @pytest.mark.asyncio
    async def test_ready_timeout_can_be_cleaned_up(self) -> None:
        worker, _ = _worker(mode="hang")

        with pytest.raises(TimeoutError, match="就绪超时"):
            await worker.start(timeout=0.01)

        await worker.stop(timeout=1.0)
        assert worker.closed

    @pytest.mark.asyncio
    async def test_stop_does_not_block_main_event_loop(self) -> None:
        worker, danmaku = _worker(mode="slow_disconnect")
        await worker.start(timeout=1.0)
        ticked = asyncio.Event()

        async def ticker() -> None:
            await asyncio.sleep(0.01)
            ticked.set()

        stop_task = asyncio.create_task(worker.stop(timeout=1.0))
        ticker_task = asyncio.create_task(ticker())

        await asyncio.wait_for(ticked.wait(), timeout=0.05)
        assert not stop_task.done()
        await asyncio.gather(stop_task, ticker_task)
        assert danmaku.disconnect_calls == 1

    @pytest.mark.asyncio
    async def test_runtime_exit_reports_failure(self) -> None:
        failures: list[tuple[int, BaseException]] = []
        worker, danmaku = _worker(failures=failures)
        await worker.start(timeout=1.0)

        danmaku.exit_unexpectedly()
        closed = await asyncio.to_thread(worker._closed_event.wait, 1.0)

        assert closed
        assert failures
        assert failures[0][0] == 100
        assert "连接中断" in str(failures[0][1])


class FakeBilibiliApi:
    def __init__(self, modes: dict[int, str]) -> None:
        self.modes = modes
        self.instances: dict[int, FakeDanmaku] = {}

    def get_live_danmaku(self, room_id: int) -> FakeDanmaku:
        danmaku = FakeDanmaku(self.modes.get(room_id, "ready"))
        self.instances[room_id] = danmaku
        return danmaku


class ManagedTestSource(BiliDanmakuSource):
    def __init__(self, api: FakeBilibiliApi, room_ids: list[int]) -> None:
        self._test_api = api
        super().__init__(
            room_id=room_ids,
            room_ready_timeout=0.2,
            room_stop_timeout=1.0,
        )

    @property
    def api(self):
        return self._test_api


def _source(api: FakeBilibiliApi, room_ids: list[int]) -> ManagedTestSource:
    source = ManagedTestSource(api, room_ids)
    source.bind(AppContext(RuntimeConfig(bilibili=object())))
    return source


class TestBiliDanmakuSourceWorkers:
    @pytest.mark.asyncio
    async def test_source_start_waits_for_every_room_ready(self) -> None:
        api = FakeBilibiliApi({100: "ready", 200: "ready"})
        source = _source(api, [100, 200])

        await source.start()

        assert source.state is SourceState.RUNNING
        assert all(worker.ready for worker in source._workers.values())
        assert (
            len(
                {
                    worker.thread.ident
                    for worker in source._workers.values()
                    if worker.thread is not None
                }
            )
            == 2
        )
        await source.stop()
        assert source._workers == {}
        assert all(
            instance.connect_thread is not None
            and not instance.connect_thread.is_alive()
            for instance in api.instances.values()
        )

    @pytest.mark.asyncio
    async def test_cross_thread_publish_failure_is_consumed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = _source(FakeBilibiliApi({}), [100])
        source.running = True
        source._main_loop = asyncio.get_running_loop()

        async def failed_publish(*args, **kwargs) -> None:
            raise RuntimeError("派发失败")

        monkeypatch.setattr(source.ctx.bus, "publish", failed_publish)
        await asyncio.to_thread(source._publish_to_main, cast(Any, object()))
        for _ in range(20):
            if source.health.state is SourceHealthState.DEGRADED:
                break
            await asyncio.sleep(0)

        assert source.health.state is SourceHealthState.DEGRADED
        assert source.health.last_error_message == "派发失败"
        assert source._publish_futures == set()

    @pytest.mark.asyncio
    async def test_dynamic_add_retains_worker_if_rollback_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = _source(FakeBilibiliApi({100: "fail"}), [999])
        source.running = True
        source._main_loop = asyncio.get_running_loop()
        original_stop = _DanmakuRoomWorker.stop

        async def failed_stop(self, timeout: float) -> None:
            raise RuntimeError("回滚失败")

        monkeypatch.setattr(_DanmakuRoomWorker, "stop", failed_stop)
        with pytest.raises(RuntimeError, match="房间 100 连接失败") as exc_info:
            await source.add_new_room(100)

        assert 100 in source._workers
        assert 100 in source.danmaku_list
        assert any("启动回滚失败" in note for note in exc_info.value.__notes__)

        monkeypatch.setattr(_DanmakuRoomWorker, "stop", original_stop)
        await source.remove_room(100)
        assert 100 not in source._workers

    @pytest.mark.asyncio
    async def test_multi_room_start_failure_rolls_back_all_threads(self) -> None:
        api = FakeBilibiliApi({100: "ready", 200: "fail"})
        source = _source(api, [100, 200])

        with pytest.raises(RuntimeError, match="房间 200 连接失败"):
            await source.start()

        assert source.state is SourceState.STOPPED
        assert not source.cleanup_required
        assert source._workers == {}
        assert source.danmaku_list == {}
        assert all(
            instance.connect_thread is not None
            and not instance.connect_thread.is_alive()
            for instance in api.instances.values()
        )
