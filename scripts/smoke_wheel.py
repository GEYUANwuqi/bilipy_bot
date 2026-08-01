"""验证从 wheel 安装的 ButterBot 最小运行时契约."""

import asyncio
import importlib.util
import subprocess
import sys
from importlib.metadata import metadata, requires, version
from pathlib import Path

import butterbot
from butterbot.app import BotApp, RuntimeConfig, SourceFactoryRegistry
from butterbot.core.event import EventBus
from butterbot.core.exceptions import ConfigError


async def _smoke() -> None:
    app = BotApp(RuntimeConfig())
    await app.close()

    assert app.closed
    assert app.bus.closed
    assert isinstance(app.bus, EventBus)


def main() -> None:
    installed_version = version("butterbot-python")
    assert butterbot.__version__ == installed_version
    provided_extras = set(metadata("butterbot-python").get_all("Provides-Extra") or ())
    assert provided_extras == {"all", "bilibili", "napcat"}
    requirements = requires("butterbot-python") or ()
    base_requirements = tuple(
        requirement for requirement in requirements if "extra ==" not in requirement
    )
    assert not any(
        requirement.lower().startswith(
            ("aiohttp", "bilibili-api-python", "pillow", "requests", "tqdm")
        )
        for requirement in base_requirements
    )
    assert importlib.util.find_spec("aiohttp") is None
    assert importlib.util.find_spec("bilibili_api") is None
    registry = SourceFactoryRegistry.with_defaults()
    assert registry.names("napcat") == ("NapcatSource",)
    assert registry.names("bilibili") == (
        "BiliDanmakuSource",
        "BiliDynamicSource",
        "BiliLiveSource",
    )
    napcat_factory = registry.get("napcat", "NapcatSource")
    assert napcat_factory is not None
    try:
        napcat_factory()
    except ConfigError as exc:
        assert "butterbot-python[napcat]" in str(exc)
    else:
        raise AssertionError("base wheel unexpectedly imported NapCat dependencies")
    config_path = Path("missing-bilibili-extra.yaml")
    config_path.write_text(
        "sources:\n  account:\n    source_name: bilibili\n",
        encoding="utf-8",
    )
    try:
        RuntimeConfig.from_yaml(config_path, environ={})
    except ConfigError as exc:
        assert "butterbot-python[bilibili]" in str(exc)
    else:
        raise AssertionError("base wheel unexpectedly imported Bilibili dependencies")
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
