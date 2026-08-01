"""验证无需 Python 包元数据的本地目录插件及混合来源契约."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from importlib.metadata import version
from pathlib import Path

from butterbot.plugin.runtime.bootstrap import PluginBootstrap
from butterbot.plugin.runtime.manager import PluginState

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "local_plugins"
PLUGIN_IDS = {
    "contract.source",
    "local.contract.combined",
    "local.contract.handler",
    "local.contract.source",
    "local.contract.hybrid-handler",
}


def _write_workspace(workspace: Path) -> tuple[Path, dict[str, Path]]:
    workspace.mkdir(parents=True)
    shutil.copytree(FIXTURES, workspace / "plugins")
    outputs = {
        "handler": workspace / "handler.out",
        "combined": workspace / "combined.out",
        "hybrid": workspace / "hybrid.out",
    }
    config = """\
plugins:
  enabled: true
  plugin_list:
    - LocalContractHandlerPlugin
    - LocalContractSourcePlugin
    - LocalContractCombinedPlugin
    - LocalContractHybridHandlerPlugin
    - ContractSourcePlugin
  plugin_path: "./plugins"
  config:
    local.contract.handler:
      output: %s
    local.contract.combined:
      output: %s
    local.contract.hybrid-handler:
      output: %s
sources:
  local-primary:
    source_name: local-contract
    kwarg:
      source: {}
  local-combined:
    source_name: local-combined
    kwarg:
      source: {}
  installed-primary:
    source_name: contract
    kwarg:
      source: {}
""" % (
        json.dumps(str(outputs["handler"])),
        json.dumps(str(outputs["combined"])),
        json.dumps(str(outputs["hybrid"])),
    )
    config_path = workspace / "config.yaml"
    config_path.write_text(config, encoding="utf-8")
    return config_path, outputs


async def _wait_for_outputs(outputs: dict[str, Path]) -> None:
    expected = {
        "handler": "local-source",
        "combined": "local-combined",
        "hybrid": "source-only",
    }
    for _ in range(100):
        if all(
            path.exists() and path.read_text(encoding="utf-8") == expected[name]
            for name, path in outputs.items()
        ):
            return
        await asyncio.sleep(0)
    raise AssertionError("本地目录插件没有完成跨来源路由")


def _assert_no_background_tasks() -> None:
    current = asyncio.current_task()
    pending = [
        task for task in asyncio.all_tasks() if task is not current and not task.done()
    ]
    assert not pending, pending


async def _run_workspace(workspace: Path) -> None:
    config_path, outputs = _write_workspace(workspace)
    validation_app = PluginBootstrap(config_path).build()
    try:
        await validation_app._prepare_plugins()
    finally:
        await validation_app.close()

    bootstrap = PluginBootstrap(config_path)
    candidates = bootstrap.inspect_candidates()
    assert "local.contract.disabled" in {
        candidate.plugin_id for candidate in candidates
    }
    app = bootstrap.build()
    manager = bootstrap.manager
    assert manager is not None
    assert set(manager.plugin_ids) == PLUGIN_IDS
    directory_statuses = [
        status for status in manager.statuses if status.origin_kind == "directory"
    ]
    assert len(directory_statuses) == 4
    assert all(status.fingerprint for status in directory_statuses)

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
    for distribution in (
        "butterbot-python",
        "butterbot-plugin-contract-source",
    ):
        version(distribution)
    assert not Path("butterbot").exists(), "smoke 必须从仓库外运行"
    assert not Path("tests").exists(), "smoke 不得依赖当前工作目录中的测试源码"

    with tempfile.TemporaryDirectory(prefix="butterbot-local-plugin-contract-") as raw:
        asyncio.run(_smoke(Path(raw)))
    print("local directory plugin smoke passed")


if __name__ == "__main__":
    main()
