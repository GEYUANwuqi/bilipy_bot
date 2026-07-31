"""验证核心与三个独立插件 wheel 的分发、路由和回滚契约."""

from __future__ import annotations

import asyncio
import os
import tempfile
from contextlib import contextmanager
from importlib import import_module
from importlib.metadata import entry_points, version
from pathlib import Path
from typing import Iterator, cast

from butterbot.core.exceptions import SourceStartError
from butterbot.plugin import (
    PluginBootstrap,
    PluginDiscoveryError,
    PluginRegistrationError,
    PluginState,
)

PLUGIN_IDS = (
    "contract.combined",
    "contract.handler",
    "contract.source",
)
PLUGIN_NAMES = (
    "ContractCombinedPlugin",
    "ContractHandlerPlugin",
    "ContractSourcePlugin",
)
FAILURE_VARIABLES = (
    "BUTTERBOT_CONTRACT_FAIL_IMPORT",
    "BUTTERBOT_CONTRACT_FAIL_REGISTER",
    "BUTTERBOT_CONTRACT_FAIL_START",
)
CONFIG = """\
plugins:
  enabled: true
  plugin_list:
    - ContractHandlerPlugin
    - ContractSourcePlugin
    - ContractCombinedPlugin
sources:
  primary:
    source_name: contract
    kwarg:
      source: {}
  secondary:
    source_name: combined
    kwarg:
      source: {}
"""


def _write_config(directory: Path) -> Path:
    path = directory / "config.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    return path


@contextmanager
def _failure(name: str) -> Iterator[None]:
    previous = os.environ.get(name)
    os.environ[name] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


async def _wait_for_routes() -> None:
    combined_received = cast(
        list[str],
        import_module("contract_combined").RECEIVED,
    )
    handler_received = cast(
        list[str],
        import_module("contract_handler").RECEIVED,
    )

    for _ in range(100):
        if handler_received == ["source-only"] and combined_received == ["combined"]:
            return
        await asyncio.sleep(0)
    raise AssertionError(
        "跨 distribution 路由未完成: "
        f"handler={handler_received!r}, combined={combined_received!r}"
    )


def _assert_no_background_tasks() -> None:
    current = asyncio.current_task()
    pending = [
        task for task in asyncio.all_tasks() if task is not current and not task.done()
    ]
    assert not pending, pending


async def _successful_start(config_path: Path) -> None:
    combined_received = cast(
        list[str],
        import_module("contract_combined").RECEIVED,
    )
    handler_received = cast(
        list[str],
        import_module("contract_handler").RECEIVED,
    )

    combined_received.clear()
    handler_received.clear()
    bootstrap = PluginBootstrap(config_path)
    app = bootstrap.build()
    manager = bootstrap.manager
    assert manager is not None

    await app.start()
    await _wait_for_routes()
    assert all(status.state == PluginState.STARTED for status in manager.statuses)

    await app.close()
    await app.close()
    assert app.manager.sources == {}
    assert app.bus.pending_callbacks == 0
    assert all(status.state == PluginState.CLOSED for status in manager.statuses)
    _assert_no_background_tasks()


def _import_failure(config_path: Path) -> None:
    with _failure("BUTTERBOT_CONTRACT_FAIL_IMPORT"):
        try:
            PluginBootstrap(config_path).build()
        except PluginDiscoveryError as exc:
            assert "ContractSourcePlugin" in str(exc)
        else:
            raise AssertionError("外部插件 import 失败未被报告")


async def _registration_failure(config_path: Path) -> None:
    bootstrap = PluginBootstrap(config_path)
    app = bootstrap.build()
    manager = bootstrap.manager
    assert manager is not None

    with _failure("BUTTERBOT_CONTRACT_FAIL_REGISTER"):
        try:
            await app.start()
        except PluginRegistrationError as exc:
            assert exc.plugin_id == "contract.handler"
        else:
            raise AssertionError("外部插件 register 失败未被报告")

    assert app.manager.sources == {}
    assert app.bus.pending_callbacks == 0
    states = {status.plugin_id: status.state for status in manager.statuses}
    assert states["contract.handler"] == PluginState.FAILED
    await app.close()
    _assert_no_background_tasks()


async def _source_start_failure(config_path: Path) -> None:
    bootstrap = PluginBootstrap(config_path)
    app = bootstrap.build()
    manager = bootstrap.manager
    assert manager is not None

    with _failure("BUTTERBOT_CONTRACT_FAIL_START"):
        try:
            await app.start()
        except SourceStartError:
            pass
        else:
            raise AssertionError("外部 Source start 失败未被报告")

    assert app.manager.sources == {}
    assert app.bus.pending_callbacks == 0
    assert all(status.state == PluginState.FAILED for status in manager.statuses)
    await app.close()
    _assert_no_background_tasks()


async def _smoke(config_path: Path) -> None:
    await _successful_start(config_path)
    _import_failure(config_path)
    await _registration_failure(config_path)
    await _source_start_failure(config_path)


def main() -> None:
    for distribution in (
        "butterbot-python",
        "butterbot-plugin-contract-source",
        "butterbot-plugin-contract-handler",
        "butterbot-plugin-contract-combined",
    ):
        version(distribution)

    discovered = {point.name for point in entry_points(group="butterbot.plugins")}
    assert set(PLUGIN_NAMES) <= discovered
    assert not Path("butterbot").exists(), "smoke 必须从仓库外运行"
    assert not Path("tests").exists(), "smoke 不得依赖测试源码"

    with tempfile.TemporaryDirectory(prefix="butterbot-plugin-contract-") as raw:
        config_path = _write_config(Path(raw))
        asyncio.run(_smoke(config_path))
    for name in FAILURE_VARIABLES:
        assert name not in os.environ
    print("plugin wheel smoke passed:", ", ".join(PLUGIN_IDS))


if __name__ == "__main__":
    main()
