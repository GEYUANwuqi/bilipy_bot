"""扩展原型所需的手动注册基础.

这里不包含插件发现、加载或 Manifest 契约。
"""

from .registrar import ExtensionRegistrar, SubscriptionSpec

__all__ = [
    "ExtensionRegistrar",
    "SubscriptionSpec",
]
