"""Tests for BaseSource template-method lifecycle (ARCH-002)."""

import asyncio

import pytest

from bilipy_bot.core.source import BaseSource
from bilipy_bot.core.types import BaseType


class StubType(BaseType):
    ALL = "stub.all"
    EVENT = "stub.event"


class StubSource(BaseSource):
    """可注入启动/停止异常的测试事件源."""

    supported_types = StubType

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_calls = 0
        self.stop_calls = 0
        self.start_exception: BaseException | None = None
        self.stop_exception: BaseException | None = None

    async def on_start(self):
        self.start_calls += 1
        if self.start_exception is not None:
            raise self.start_exception

    async def on_stop(self):
        self.stop_calls += 1
        if self.stop_exception is not None:
            raise self.stop_exception


class TestBaseSourceLifecycle:
    """start/stop 模板方法对 running 的管理."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        """start 成功后 running 应为 True."""
        source = StubSource()
        await source.start()
        assert source.running
        assert source.start_calls == 1

    @pytest.mark.asyncio
    async def test_start_twice_is_noop(self):
        """已运行时再次 start 不应重复调用 on_start."""
        source = StubSource()
        await source.start()
        await source.start()
        assert source.start_calls == 1

    @pytest.mark.asyncio
    async def test_stop_clears_running(self):
        """stop 后 running 应为 False."""
        source = StubSource()
        await source.start()
        await source.stop()
        assert not source.running
        assert source.stop_calls == 1

    @pytest.mark.asyncio
    async def test_stop_when_not_running_is_noop(self):
        """未运行时 stop 不应调用 on_stop."""
        source = StubSource()
        await source.stop()
        assert source.stop_calls == 0


class TestBaseSourceStartFailure:
    """on_start 失败必须回滚 running（ARCH-002）."""

    @pytest.mark.asyncio
    async def test_start_failure_rolls_back_running(self):
        """on_start 抛异常时 running 应回滚为 False."""
        source = StubSource()
        source.start_exception = RuntimeError("连接失败")

        with pytest.raises(RuntimeError, match="连接失败"):
            await source.start()

        assert not source.running

    @pytest.mark.asyncio
    async def test_start_failure_propagates_original_exception(self):
        """原始异常应原样向上传播，不被包装."""
        original = ValueError("凭证无效")
        source = StubSource()
        source.start_exception = original

        with pytest.raises(ValueError) as excinfo:
            await source.start()

        assert excinfo.value is original

    @pytest.mark.asyncio
    async def test_start_cancellation_rolls_back_running(self):
        """CancelledError 不是 Exception 的子类，也必须回滚 running."""
        source = StubSource()
        source.start_exception = asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await source.start()

        assert not source.running

    @pytest.mark.asyncio
    async def test_can_retry_start_after_failure(self):
        """回滚后应能再次尝试启动（running 未被卡在 True）."""
        source = StubSource()
        source.start_exception = RuntimeError("第一次失败")

        with pytest.raises(RuntimeError):
            await source.start()

        source.start_exception = None
        await source.start()
        assert source.running
        assert source.start_calls == 2
