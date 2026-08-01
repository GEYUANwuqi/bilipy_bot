"""Tests for BaseSource template-method lifecycle (ARCH-002)."""

import asyncio

import pytest

from butterbot.core.exceptions import LifecycleError
from butterbot.core.source import (
    BaseSource,
    SourceHealthState,
    SourceState,
)
from butterbot.core.types import BaseType


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

    def test_unknown_constructor_keyword_is_rejected(self):
        """拼错构造参数不能被 **kwargs 静默吞掉."""
        with pytest.raises(TypeError, match="unexpected_option"):
            StubSource(unexpected_option=True)

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        """start 成功后 running 应为 True."""
        source = StubSource()
        await source.start()
        assert source.running
        assert source.state is SourceState.RUNNING
        assert source.cleanup_required
        assert source.health.state is SourceHealthState.READY
        assert source.health.last_success_at is not None
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
        assert source.state is SourceState.STOPPED
        assert not source.cleanup_required
        assert source.health.state is SourceHealthState.STOPPED
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
        assert source.state is SourceState.STOPPED
        assert not source.cleanup_required
        assert source.health.state is SourceHealthState.STOPPED
        assert source.health.last_error_type == "RuntimeError"
        assert source.health.last_error_message == "连接失败"
        assert source.stop_calls == 1

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


class TestBaseSourceStopFailure:
    """停止失败必须保留清理责任并允许重试."""

    @pytest.mark.asyncio
    async def test_stop_failure_can_be_retried(self):
        source = StubSource()
        await source.start()
        source.stop_exception = RuntimeError("第一次清理失败")

        with pytest.raises(RuntimeError, match="第一次清理失败"):
            await source.stop()

        assert not source.running
        assert source.state is SourceState.STOP_FAILED
        assert source.cleanup_required
        assert source.health.state is SourceHealthState.DEGRADED
        assert source.health.last_error_type == "RuntimeError"
        assert source.stop_calls == 1

        source.stop_exception = None
        await source.stop()

        assert source.state is SourceState.STOPPED
        assert not source.cleanup_required
        assert source.health.state is SourceHealthState.STOPPED
        assert source.stop_calls == 2

    @pytest.mark.asyncio
    async def test_start_is_rejected_until_failed_cleanup_succeeds(self):
        source = StubSource()
        source.start_exception = RuntimeError("启动失败")
        source.stop_exception = RuntimeError("回滚失败")

        with pytest.raises(RuntimeError, match="启动失败") as exc_info:
            await source.start()

        assert source.state is SourceState.STOP_FAILED
        assert source.cleanup_required
        assert any("启动回滚失败" in note for note in exc_info.value.__notes__)

        with pytest.raises(LifecycleError, match="重试 stop"):
            await source.start()

        source.stop_exception = None
        await source.stop()
        source.start_exception = None
        await source.start()
        assert source.state is SourceState.RUNNING


class GatedSource(BaseSource):
    """用于验证并发生命周期调用只执行一次."""

    supported_types = StubType

    def __init__(self):
        super().__init__()
        self.start_calls = 0
        self.stop_calls = 0
        self.start_entered = asyncio.Event()
        self.start_release = asyncio.Event()
        self.stop_entered = asyncio.Event()
        self.stop_release = asyncio.Event()

    async def on_start(self):
        self.start_calls += 1
        self.start_entered.set()
        await self.start_release.wait()

    async def on_stop(self):
        self.stop_calls += 1
        self.stop_entered.set()
        await self.stop_release.wait()


class TestBaseSourceConcurrency:
    """同一 Source 的生命周期调用必须串行且幂等."""

    @pytest.mark.asyncio
    async def test_concurrent_start_runs_callback_once(self):
        source = GatedSource()
        first = asyncio.create_task(source.start())
        second = asyncio.create_task(source.start())

        await source.start_entered.wait()
        source.start_release.set()
        await asyncio.gather(first, second)

        assert source.start_calls == 1
        assert source.state is SourceState.RUNNING

    @pytest.mark.asyncio
    async def test_concurrent_stop_runs_callback_once(self):
        source = GatedSource()
        source.start_release.set()
        await source.start()

        first = asyncio.create_task(source.stop())
        second = asyncio.create_task(source.stop())
        await source.stop_entered.wait()
        source.stop_release.set()
        await asyncio.gather(first, second)

        assert source.stop_calls == 1
        assert source.state is SourceState.STOPPED
