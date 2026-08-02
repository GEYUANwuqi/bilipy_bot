"""插件示例使用的最小 CLI 应用入口."""

from butterbot.app import BotApp, RuntimeConfig


def app(
    *,
    config: RuntimeConfig,
    cli_mode: bool = True,
) -> BotApp:
    """接收 CLI 解析完成的配置和宿主模式."""
    return BotApp(config=config, cli_mode=cli_mode)
