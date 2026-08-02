"""验证外部 Handler wheel 与应用自有 Source 的装配和回滚契约."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from contextlib import contextmanager
from importlib import import_module
from importlib.metadata import entry_points, version
from pathlib import Path
from typing import Iterator, cast

from butterbot.app import BotApp
from butterbot.core import BaseDataMixin, BaseSource, BaseType, Event
from butterbot.core.exceptions import SourceStartError
from butterbot.plugin import PluginDiscoveryError, PluginRegistrationError
from butterbot.plugin.runtime.manager import PluginState

PLUGIN_ID = "contract.handler"
PLUGIN_NAME = "ContractHandlerPlugin"
FAILURE_VARIABLES = (
    "BUTTERBOT_CONTRACT_FAIL_IMPORT",
    "BUTTERBOT_CONTRACT_FAIL_REGISTER",
    "BUTTERBOT_CONTRACT_FAIL_START",
)
CONFIG = """\
plugins:
  enabled: true
  plugin_list: [ContractHandlerPlugin]
sources: {}
"""


class ContractType(BaseType):
    ALL = "contract.all"
    MESSAGE = "contract.message"


class ContractData(BaseDataMixin):
    def __init__(self, value: str) -> None:
        self.value = value


class ContractSource(BaseSource):
    source_kind = "contract.events"
    supported_types = ContractType

    async def on_start(self) -> None:
        if os.environ.get("BUTTERBOT_CONTRACT_FAIL_START"):
            raise RuntimeError("application source start failed")
        await self.ctx.bus.publish(
            self.uuid,
            Event(ContractData("application-source"), ContractType.MESSAGE),
        )

    async def on_stop(self) -> None:
        pass


def _write_config(directory: Path) -> Path:
    path = directory / "config.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    return path


def _build_app(config_path: Path) -> BotApp:
    app = BotApp(
        config_path=config_path,
        cli_mode=False,
        logging_mode="external",
    )
    app.add_source(ContractSource, config_key="primary")
    return app


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


def _received() -> list[str]:
    return cast(list[str], import_module("contract_handler").RECEIVED)


def _assert_no_background_tasks() -> None:
    current = asyncio.current_task()
    pending = [
        task for task in asyncio.all_tasks() if task is not current and not task.done()
    ]
    assert not pending, pending


async def _successful_start(config_path: Path) -> None:
    received = _received()
    received.clear()
    app = _build_app(config_path)
    manager = app._optional_runtime
    assert manager is not None

    await app.start()
    for _ in range(100):
        if received == ["application-source"]:
            break
        await asyncio.sleep(0)
    assert received == ["application-source"]
    assert manager.statuses[0].state == PluginState.STARTED

    await app.close()
    await app.close()
    assert app.manager.sources == {}
    assert app.bus.pending_callbacks == 0
    assert manager.statuses[0].state == PluginState.CLOSED
    _assert_no_background_tasks()


def _import_failure(config_path: Path) -> None:
    for name in tuple(sys.modules):
        if name == "contract_handler":
            sys.modules.pop(name, None)
    with _failure("BUTTERBOT_CONTRACT_FAIL_IMPORT"):
        try:
            _build_app(config_path)
        except PluginDiscoveryError:
            pass
        else:
            raise AssertionError("外部插件 import 失败未被报告")


async def _registration_failure(config_path: Path) -> None:
    app = _build_app(config_path)
    manager = app._optional_runtime
    assert manager is not None
    with _failure("BUTTERBOT_CONTRACT_FAIL_REGISTER"):
        try:
            await app.start()
        except PluginRegistrationError as exc:
            assert exc.plugin_id == PLUGIN_ID
        else:
            raise AssertionError("外部插件 Handler 注册失败未被报告")
    assert app.bus.pending_callbacks == 0
    assert manager.statuses[0].state == PluginState.FAILED
    await app.close()
    _assert_no_background_tasks()


async def _source_start_failure(config_path: Path) -> None:
    app = _build_app(config_path)
    manager = app._optional_runtime
    assert manager is not None
    with _failure("BUTTERBOT_CONTRACT_FAIL_START"):
        try:
            await app.start()
        except SourceStartError:
            pass
        else:
            raise AssertionError("应用 Source start 失败未被报告")
    assert app.bus.pending_callbacks == 0
    assert manager.statuses[0].state == PluginState.FAILED
    await app.close()
    _assert_no_background_tasks()


async def _smoke(config_path: Path) -> None:
    await _successful_start(config_path)
    await _registration_failure(config_path)
    await _source_start_failure(config_path)
    _import_failure(config_path)


def main() -> None:
    version("butterbot-python")
    version("butterbot-plugin-contract-handler")
    discovered = {point.name for point in entry_points(group="butterbot.plugins")}
    assert PLUGIN_NAME in discovered
    assert not Path("butterbot").exists(), "smoke 必须从仓库外运行"
    assert not Path("tests").exists(), "smoke 不得依赖测试源码"

    with tempfile.TemporaryDirectory(prefix="butterbot-plugin-contract-") as raw:
        asyncio.run(_smoke(_write_config(Path(raw))))
    for name in FAILURE_VARIABLES:
        assert name not in os.environ
    print("plugin wheel smoke passed:", PLUGIN_ID)


if __name__ == "__main__":
    main()
