"""轮询事件源共享契约测试（ARCH-005）."""

import pytest

from butterbot.sources.bilibili.source.base_polling_source import BasePollingSource
from butterbot.sources.bilibili.source.bili_danmaku_source import BiliDanmakuSource
from butterbot.sources.bilibili.source.bili_dynamic_source import BiliDynamicSource
from butterbot.sources.bilibili.source.bili_live_source import BiliLiveSource


class TestSharedPollingSource:
    def test_both_pollers_use_shared_lifecycle(self) -> None:
        """动态源与直播源共用同一生命周期实现."""
        assert issubclass(BiliDynamicSource, BasePollingSource)
        assert issubclass(BiliLiveSource, BasePollingSource)

    def test_target_management_keeps_existing_public_views(self) -> None:
        """抽取目标管理后保留既有 members/rooms 视图."""
        dynamic = BiliDynamicSource(watch_targets=[1, 2, 1])
        live = BiliLiveSource(watch_targets=[10, 20, 10])

        assert dynamic.members == [1, 2]
        assert live.rooms == [10, 20]

        dynamic.remove_members([1])
        live.remove_members([10])
        assert dynamic.members == [2]
        assert live.rooms == [20]

    @pytest.mark.asyncio
    async def test_shared_stop_cancels_and_releases_monitor_task(self) -> None:
        """停止时取消、等待并释放共享监控任务."""
        source = BiliDynamicSource()
        source.running = True
        await source.on_start()
        task = source._task

        await source.on_stop()

        assert task is not None and task.done()
        assert source._task is None


class TestDanmakuConstructorCompatibility:
    def test_watch_targets_alias(self) -> None:
        """弹幕源支持与其他 Bilibili 源一致的 watch_targets."""
        source = BiliDanmakuSource(watch_targets=[100, 200])
        assert source.room_id == [100, 200]

    def test_room_id_remains_supported(self) -> None:
        """旧 room_id 参数保持兼容."""
        source = BiliDanmakuSource(room_id=[100])
        assert source.room_id == [100]

    def test_conflicting_target_arguments_are_rejected(self) -> None:
        """同时提供新旧参数时尽早给出明确错误."""
        with pytest.raises(TypeError, match="room_id.*watch_targets"):
            BiliDanmakuSource(room_id=[100], watch_targets=[200])
