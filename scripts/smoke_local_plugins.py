"""验证本地 Handler 插件消费应用自有 Source 的目录隔离契约."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from importlib.metadata import version
from pathlib import Path

from butterbot.app import BotApp
from butterbot.core import BaseDataMixin, BaseSource, BaseType, Event
from butterbot.plugin.discovery.catalog import PluginCatalog
from butterbot.plugin.discovery.settings import LocalPluginSettings
from butterbot.plugin.runtime.manager import PluginState

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "local_plugins"
PLUGIN_IDS = {
    "local.contract.handler",
    "local.contract.hybrid-handler",
}


class LocalType(BaseType):
    ALL = "local-contract.all"
    MESSAGE = "local-contract.message"


class InstalledType(BaseType):
    ALL = "contract.all"
    MESSAGE = "contract.message"


class SmokeData(BaseDataMixin):
    def __init__(self, value: str) -> None:
        self.value = value


class LocalSource(BaseSource):
    source_kind = "local-contract.events"
    supported_types = LocalType

    async def on_start(self) -> None:
        await self.ctx.bus.publish(
            self.uuid,
            Event(SmokeData("local-source"), LocalType.MESSAGE),
        )

    async def on_stop(self) -> None:
        pass


class InstalledKindSource(BaseSource):
    source_kind = "contract.events"
    supported_types = InstalledType

    async def on_start(self) -> None:
        await self.ctx.bus.publish(
            self.uuid,
            Event(SmokeData("application-source"), InstalledType.MESSAGE),
        )

    async def on_stop(self) -> None:
        pass


def _write_workspace(workspace: Path) -> tuple[Path, dict[str, Path]]:
    workspace.mkdir(parents=True)
    shutil.copytree(FIXTURES, workspace / "plugins")
    outputs = {
        "handler": workspace / "handler.out",
        "hybrid": workspace / "hybrid.out",
    }
    config = """\
plugins:
  enabled: true
  plugin_list:
    - LocalContractHandlerPlugin
    - LocalContractHybridHandlerPlugin
  plugin_path: "./plugins"
  config:
    local.contract.handler:
      output: %s
    local.contract.hybrid-handler:
      output: %s
sources: {}
""" % (
        json.dumps(str(outputs["handler"])),
        json.dumps(str(outputs["hybrid"])),
    )
    config_path = workspace / "config.yaml"
    config_path.write_text(config, encoding="utf-8")
    return config_path, outputs


async def _wait_for_outputs(outputs: dict[str, Path]) -> None:
    expected = {
        "handler": "local-source",
        "hybrid": "application-source",
    }
    for _ in range(100):
        if all(
            path.exists() and path.read_text(encoding="utf-8") == expected[name]
            for name, path in outputs.items()
        ):
            return
        await asyncio.sleep(0)
    raise AssertionError("本地目录 Handler 没有完成应用 Source 路由")


def _assert_no_background_tasks() -> None:
    current = asyncio.current_task()
    pending = [
        task for task in asyncio.all_tasks() if task is not current and not task.done()
    ]
    assert not pending, pending


async def _run_workspace(workspace: Path) -> None:
    config_path, outputs = _write_workspace(workspace)
    candidates = PluginCatalog.index_candidates(
        local=LocalPluginSettings(path="./plugins"),
        config_root=workspace,
    )
    assert "local.contract.disabled" in {
        candidate.plugin_id for candidate in candidates
    }

    app = BotApp(
        config_path=config_path,
        cli_mode=False,
        logging_mode="external",
    )
    app.add_source(LocalSource, config_key="local")
    app.add_source(InstalledKindSource, config_key="installed-kind")
    manager = app._optional_runtime
    assert manager is not None
    assert set(manager.plugin_ids) == PLUGIN_IDS
    assert all(status.fingerprint for status in manager.statuses)

    await app.start()
    await _wait_for_outputs(outputs)
    assert all(status.state == PluginState.STARTED for status in manager.statuses)
    await app.close()
    assert app.manager.sources == {}
    assert app.bus.pending_callbacks == 0
    assert all(status.state == PluginState.CLOSED for status in manager.statuses)
    _assert_no_background_tasks()


async def _smoke(root: Path) -> None:
    await _run_workspace(root / "first-absolute-location")
    await _run_workspace(root / "different" / "second-location")


def main() -> None:
    version("butterbot-python")
    assert not Path("butterbot").exists(), "smoke 必须从仓库外运行"
    assert not Path("tests").exists(), "smoke 不得依赖当前工作目录中的测试源码"

    with tempfile.TemporaryDirectory(prefix="butterbot-local-plugin-contract-") as raw:
        asyncio.run(_smoke(Path(raw)))
    print("local directory plugin smoke passed")


if __name__ == "__main__":
    main()
