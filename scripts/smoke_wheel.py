"""验证从 wheel 安装的 ButterBot 最小运行时契约."""

import asyncio
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

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
    cli = Path(sys.executable).with_name("butterbot")
    result = subprocess.run(
        [str(cli), "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == installed_version
    asyncio.run(_smoke())
    print("wheel smoke passed:", installed_version)


if __name__ == "__main__":
    main()
