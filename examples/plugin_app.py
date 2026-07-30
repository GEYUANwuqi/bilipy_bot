"""实验插件示例使用的最小 BotApp factory."""

from butterbot.app import BotApp, RuntimeConfig, SourceFactoryRegistry
from butterbot.utils import setup_logging


def create_app(
    *,
    config: RuntimeConfig,
    source_factory_registry: SourceFactoryRegistry,
) -> BotApp:
    """让 PluginBootstrap 在构造应用前注入插件注册项."""
    setup_logging("DEBUG")
    return BotApp(
        config=config,
        source_factory_registry=source_factory_registry,
    )
