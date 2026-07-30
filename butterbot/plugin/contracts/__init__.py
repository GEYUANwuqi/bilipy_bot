"""插件作者面对的稳定形状契约."""

from .descriptor import PluginDescriptor
from .hooks import ButterPlugin
from .routing import SourceRef, SubscriptionSpec

__all__ = [
    "ButterPlugin",
    "PluginDescriptor",
    "SourceRef",
    "SubscriptionSpec",
]
