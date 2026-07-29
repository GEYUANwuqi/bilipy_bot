"""butterbot 应用入口模块.

用户应该从这里导入需要的类，而不是直接从 core 导入。
"""

from butterbot.core.event import Event
from butterbot.core.exceptions import (
    ApiError,
    ButterError,
    ConfigError,
    LifecycleError,
    SourceError,
    SourceStartError,
    SubscriptionError,
)
from butterbot.core.filter import AndFilter, BaseFilter, OrFilter

from .bot_app import BotApp
from .config import (
    BuilderRegistration,
    ConfigBuilderRegistry,
    RuntimeConfig,
    SourceDefinition,
    register_builder,
)
from .extensions import ExtensionRegistrar, SubscriptionSpec
from .source_factory import SourceFactoryRegistry

__all__ = [
    # 应用主入口
    "BotApp",
    # 事件
    "Event",
    # 配置
    "BuilderRegistration",
    "ConfigBuilderRegistry",
    "ExtensionRegistrar",
    "RuntimeConfig",
    "SourceDefinition",
    "SourceFactoryRegistry",
    "SubscriptionSpec",
    "register_builder",
    # 过滤器
    "AndFilter",
    "BaseFilter",
    "OrFilter",
    # 异常层级
    "ApiError",
    "ButterError",
    "ConfigError",
    "LifecycleError",
    "SourceError",
    "SourceStartError",
    "SubscriptionError",
]
