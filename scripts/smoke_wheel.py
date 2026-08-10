"""验证从 wheel 安装的 ButterBot 最小运行时契约."""

import asyncio
import importlib.util
import subprocess
import sys
from importlib.metadata import metadata, requires, version
from pathlib import Path

import butterbot
import butterbot.app as app_module
from butterbot.app import BotApp, RuntimeConfig
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
    assert provided_extras == {"all", "bilibili", "lark", "napcat"}
    requirements = requires("butterbot-python") or ()
    base_requirements = tuple(
        requirement for requirement in requirements if "extra ==" not in requirement
    )
    assert not any(
        requirement.lower().startswith(
            (
                "aiohttp",
                "bilibili-api-python",
                "lark-oapi",
                "pillow",
                "requests",
                "tqdm",
            )
        )
        for requirement in base_requirements
    )
    assert importlib.util.find_spec("aiohttp") is None
    assert importlib.util.find_spec("bilibili_api") is None
    assert importlib.util.find_spec("lark_oapi") is None
    assert not hasattr(app_module, "SourceFactoryRegistry")
    missing_extra_configs = {
        "napcat": (
            "sources:\n"
            "  account:\n"
            "    source_name: napcat\n"
            "    url: ws://localhost:3001\n"
        ),
        "bilibili": "sources:\n  account:\n    source_name: bilibili\n",
        "lark": (
            "sources:\n"
            "  account:\n"
            "    source_name: lark\n"
            "    app_id: cli_test\n"
            "    app_secret: secret\n"
        ),
    }
    for extra, payload in missing_extra_configs.items():
        config_path = Path("missing-%s-extra.yaml" % extra)
        config_path.write_text(payload, encoding="utf-8")
        try:
            RuntimeConfig.from_yaml(config_path, environ={})
        except ConfigError as exc:
            assert "butterbot-python[%s]" % extra in str(exc)
        else:
            raise AssertionError(
                "base wheel unexpectedly imported %s dependencies" % extra
            )
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
