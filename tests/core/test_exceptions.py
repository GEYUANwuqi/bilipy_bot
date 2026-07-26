"""Tests for the framework exception hierarchy (ERR-001)."""

import pytest

from butterbot.core.exceptions import (
    ApiError,
    ButterError,
    ConfigError,
    LifecycleError,
    SourceError,
    SourceStartError,
    SubscriptionError,
)


class TestExceptionHierarchy:
    """所有框架异常都应能被单一的 ButterError 兜住."""

    @pytest.mark.parametrize(
        "exc_cls",
        [
            ApiError,
            ConfigError,
            LifecycleError,
            SourceError,
            SubscriptionError,
        ],
    )
    def test_inherits_butter_error(self, exc_cls):
        """每个具体异常都应是 ButterError 的子类."""
        assert issubclass(exc_cls, ButterError)

    def test_source_start_error_is_source_error(self):
        """SourceStartError 应归属 SourceError 分支."""
        assert issubclass(SourceStartError, SourceError)
        assert issubclass(SourceStartError, ButterError)

    def test_config_error_is_value_error(self):
        """ConfigError 同时继承 ValueError，兼容原有 except ValueError 的调用方."""
        assert issubclass(ConfigError, ValueError)

    def test_lifecycle_error_is_runtime_error(self):
        """LifecycleError 同时继承 RuntimeError，兼容原有 except RuntimeError."""
        assert issubclass(LifecycleError, RuntimeError)

    def test_subscription_error_is_value_error(self):
        """SubscriptionError 同时继承 ValueError（订阅规则是个非法取值）."""
        assert issubclass(SubscriptionError, ValueError)

    def test_catchable_as_butter_error(self):
        """具体异常应能被 except ButterError 捕获."""
        with pytest.raises(ButterError):
            raise ConfigError("boom")


class TestSourceStartError:
    """SourceStartError 需保留每个失败源的原始异常."""

    def test_failures_preserved(self):
        """failures 应保留原始异常对象本身，而不只是字符串."""
        original = ValueError("凭证无效")
        err = SourceStartError({"StubSource(uuid=1)": original})
        assert err.failures["StubSource(uuid=1)"] is original

    def test_message_lists_all_failures(self):
        """异常消息应列出全部失败的事件源."""
        err = SourceStartError(
            {"A": RuntimeError("a 挂了"), "B": RuntimeError("b 挂了")}
        )
        message = str(err)
        assert "A" in message
        assert "B" in message
        assert "a 挂了" in message

    def test_failures_is_a_copy(self):
        """外部修改传入的 dict 不应影响已构造的异常."""
        source = {"A": RuntimeError("boom")}
        err = SourceStartError(source)
        source.clear()
        assert "A" in err.failures
