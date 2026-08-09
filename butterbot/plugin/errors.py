"""插件控制面的异常类型."""

from __future__ import annotations

from butterbot.core.exceptions import ButterError, SourceError


class PluginError(ButterError):
    """插件系统错误的基类."""


class PluginDiscoveryError(PluginError):
    """插件发现、导入或身份校验失败."""


class PluginCompatibilityError(PluginError):
    """插件与当前核心版本或能力集合不兼容."""


class PluginDependencyError(PluginError):
    """插件依赖缺失或形成循环."""


class PluginRegistrationError(PluginError):
    """插件在配置、注册或启动阶段失败."""

    def __init__(
        self,
        plugin_id: str,
        phase: str,
        cause: BaseException,
    ) -> None:
        self.plugin_id = plugin_id
        self.phase = phase
        self.cause = cause
        message = "插件 '%s' 在 %s 阶段失败（%s）" % (
            plugin_id,
            phase,
            type(cause).__name__,
        )
        if isinstance(cause, SourceError) and str(cause):
            message = "%s: %s" % (message, cause)
        super().__init__(message)


__all__ = [
    "PluginCompatibilityError",
    "PluginDependencyError",
    "PluginDiscoveryError",
    "PluginError",
    "PluginRegistrationError",
]
