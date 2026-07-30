"""目录插件与 distribution 插件共享的统一基类."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from butterbot.plugin.runtime.registrar import ConfigRegistrar, PluginRegistrar


class ButterPlugin:
    """本地目录和 distribution 插件共享的唯一用户基类.

    本地插件的 descriptor 来自 ``plugin.toml``；distribution 插件在子类上
    声明 ``descriptor``。所有 hook 都提供空实现，插件只需覆盖实际使用的阶段。
    """

    def register_config(self, registrar: ConfigRegistrar) -> None:
        """登记配置 builder 和 Source factory，不产生运行时任务."""
        del registrar

    async def register(self, registrar: PluginRegistrar) -> None:
        """登记 Source、Handler 和清理回调."""
        del registrar

    async def on_start(self) -> None:
        """全部 Source 启动成功后执行."""

    async def on_stop(self) -> None:
        """停止 Source 和撤销插件注册前执行."""


__all__ = ["ButterPlugin"]
