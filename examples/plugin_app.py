"""插件示例使用的最小 CLI 应用入口."""

from butterbot.app import BotApp, RuntimeConfig, SourceFactoryRegistry
from butterbot.utils import setup_logging


def app(
    *,
    config: RuntimeConfig,
    source_factory_registry: SourceFactoryRegistry,
) -> BotApp:
    """接收 CLI 解析的配置和插件扩展后的 Source 注册表."""
    setup_logging("DEBUG")
    return BotApp(
        config=config,
        source_factory_registry=source_factory_registry,
    )
