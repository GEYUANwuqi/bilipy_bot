"""验证从 wheel 安装的 ButterBot 最小运行时契约."""

import asyncio
from importlib.metadata import version

import butterbot
from butterbot.app import BotApp, RuntimeConfig
from butterbot.core.event import EventBus


async def _smoke() -> None:
    app = BotApp(RuntimeConfig())
    await app.close()

    assert app.closed
    assert app.bus.closed
    assert isinstance(app.bus, EventBus)


def main() -> None:
    installed_version = version("butterbot-python")
    assert butterbot.__version__ == installed_version
    asyncio.run(_smoke())
    print("wheel smoke passed:", installed_version)


if __name__ == "__main__":
    main()
