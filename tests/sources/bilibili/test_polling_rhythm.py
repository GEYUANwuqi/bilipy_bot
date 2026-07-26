"""Tests for polling cadence of the bilibili polling sources (BUG-001).

``poll_interval`` 是「每轮」的间隔，不是「每个目标」的间隔。原实现把
``sleep`` 放在 per-target 的内层循环里，单个目标的实际刷新周期变成
``N × interval``（监控 10 个 uid、interval=60 时要 600s 才轮到一次）。

这里不碰真实 B 站 API：直接覆写 ``_poll_dynamic`` / ``_poll_live``
只做计数，用一个被打过桩的 ``asyncio.sleep`` 记录每次等待的时长。
"""

import asyncio

import pytest

from butterbot.sources.bilibili.source.bili_dynamic_source import BiliDynamicSource
from butterbot.sources.bilibili.source.bili_live_source import BiliLiveSource

_REAL_SLEEP = asyncio.sleep
"""打桩前先抓住真正的 asyncio.sleep.

打桩改的是共享的 ``asyncio`` 模块属性，若 recorder 内部再调
``asyncio.sleep`` 会调到自己身上，把等待次数算重。
"""


class _SleepRecorder:
    """替换 asyncio.sleep：记录每次等待时长，并在够多轮之后中断循环."""

    def __init__(self, stop_after: int) -> None:
        self.delays: list[float] = []
        self._stop_after = stop_after

    async def __call__(self, delay: float, *_args, **_kwargs) -> None:
        self.delays.append(delay)
        if len(self.delays) >= self._stop_after:
            raise asyncio.CancelledError()
        # 让出控制权但不真的等待，保持测试快速
        await _REAL_SLEEP(0)


class RecordingDynamicSource(BiliDynamicSource):
    """只记录轮询次数的动态源（不触碰真实 API）."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.polled: list[int] = []

    async def _poll_dynamic(self, uid: int) -> None:
        self.polled.append(uid)


class RecordingLiveSource(BiliLiveSource):
    """只记录轮询次数的直播源（不触碰真实 API）."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.polled: list[int] = []

    async def _poll_live(self, room_id: int) -> None:
        self.polled.append(room_id)


class TestDynamicPollingRhythm:
    """动态源：每轮只 sleep 一次."""

    @pytest.mark.asyncio
    async def test_sleeps_once_per_round_not_per_uid(self, monkeypatch):
        """监控 3 个 uid 时，一轮应产生 3 次轮询但只有 1 次 sleep."""
        source = RecordingDynamicSource(poll_interval=60, watch_targets=[1, 2, 3])
        recorder = _SleepRecorder(stop_after=1)
        monkeypatch.setattr(asyncio, "sleep", recorder)

        source.running = True
        await source._monitor_loop()

        assert source.polled == [1, 2, 3]
        assert recorder.delays == [60]

    @pytest.mark.asyncio
    async def test_interval_is_per_round_across_rounds(self, monkeypatch):
        """连续两轮：每轮各一次 sleep，总时长为 2×interval 而非 6×interval."""
        source = RecordingDynamicSource(poll_interval=30, watch_targets=[1, 2, 3])
        recorder = _SleepRecorder(stop_after=2)
        monkeypatch.setattr(asyncio, "sleep", recorder)

        source.running = True
        await source._monitor_loop()

        assert source.polled == [1, 2, 3, 1, 2, 3]
        assert recorder.delays == [30, 30]
        assert sum(recorder.delays) == 60  # 不是 6×30=180

    @pytest.mark.asyncio
    async def test_poll_num_counts_rounds(self, monkeypatch):
        """poll_num 应按轮次递增."""
        source = RecordingDynamicSource(poll_interval=10, watch_targets=[1, 2])
        recorder = _SleepRecorder(stop_after=3)
        monkeypatch.setattr(asyncio, "sleep", recorder)

        source.running = True
        await source._monitor_loop()

        assert source.poll_num == 3

    @pytest.mark.asyncio
    async def test_empty_target_list_waits_without_polling(self, monkeypatch):
        """无监控目标时应短暂等待，不产生轮询."""
        source = RecordingDynamicSource(poll_interval=60)
        recorder = _SleepRecorder(stop_after=1)
        monkeypatch.setattr(asyncio, "sleep", recorder)

        source.running = True
        await source._monitor_loop()

        assert source.polled == []
        assert recorder.delays == [5]  # 空列表分支的固定等待


class TestLivePollingRhythm:
    """直播源：每轮只 sleep 一次."""

    @pytest.mark.asyncio
    async def test_sleeps_once_per_round_not_per_room(self, monkeypatch):
        """监控 3 个房间时，一轮应产生 3 次轮询但只有 1 次 sleep."""
        source = RecordingLiveSource(poll_interval=60, watch_targets=[10, 20, 30])
        recorder = _SleepRecorder(stop_after=1)
        monkeypatch.setattr(asyncio, "sleep", recorder)

        source.running = True
        await source._monitor_loop()

        assert source.polled == [10, 20, 30]
        assert recorder.delays == [60]

    @pytest.mark.asyncio
    async def test_interval_is_per_round_across_rounds(self, monkeypatch):
        """连续两轮的等待总时长应为 2×interval."""
        source = RecordingLiveSource(poll_interval=45, watch_targets=[10, 20])
        recorder = _SleepRecorder(stop_after=2)
        monkeypatch.setattr(asyncio, "sleep", recorder)

        source.running = True
        await source._monitor_loop()

        assert source.polled == [10, 20, 10, 20]
        assert recorder.delays == [45, 45]
