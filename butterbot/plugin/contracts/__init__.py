"""插件作者面对的 Beta 形状契约."""

from .config import PluginConfig
from .context import PluginContext, PluginScope
from .descriptor import PluginDescriptor
from .hooks import ButterPlugin, register
from .routing import SourceRef, SubscriptionSpec

__all__ = [
    "ButterPlugin",
    "PluginConfig",
    "PluginContext",
    "PluginDescriptor",
    "PluginScope",
    "SourceRef",
    "SubscriptionSpec",
    "register",
]
