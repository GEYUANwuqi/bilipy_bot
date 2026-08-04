"""统一运行时装配与可选插件生命周期测试."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

from butterbot.app import BotApp, RuntimeConfig
from butterbot.core.data import BaseDataMixin
from butterbot.core.event import Event
from butterbot.core.source import BaseSource
from butterbot.core.types import BaseType
from butterbot.plugin import PluginRegistrationError


class RuntimeType(BaseType):
    ALL = "runtime.all"
    MESSAGE = "runtime.message"


class RuntimeData(BaseDataMixin):
    def __init__(self, value: str) -> None:
        self.value = value


class RuntimeSource(BaseSource):
    source_kind = "runtime.events"
    supported_types = RuntimeType

    async def on_start(self) -> None:
        await self.ctx.bus.publish(
            self.uuid,
            Event(RuntimeData("ready"), RuntimeType.MESSAGE),
        )

    async def on_stop(self) -> None:
        pass


class FailingSource(RuntimeSource):
    async def on_start(self) -> None:
        raise RuntimeError("source failed")


def _write_plugin(
    root: Path,
    *,
    plugin_id: str = "local.runtime-handler",
    plugin_name: str = "RuntimeHandlerPlugin",
    code: str,
) -> Path:
    plugin_root = root / plugin_id
    plugin_root.mkdir(parents=True)
    plugin_root.joinpath("plugin.toml").write_text(
        "schema_version = 2\n"
        f'plugin_name = "{plugin_name}"\n'
        'version = "0.1.0"\n'
        'requires_core = ">=3.1,<4"\n'
        'entry = "plugin.py"\n'
        "requires_plugins = []\n"
        "requires_distributions = []\n",
        encoding="utf-8",
    )
    plugin_root.joinpath("plugin.py").write_text(code, encoding="utf-8")
    return plugin_root


def _write_config(
    root: Path,
    *,
    enabled: bool = True,
    plugin_name: str = "RuntimeHandlerPlugin",
    private_config: str = "",
    lifecycle_config: str = "",
) -> Path:
    path = root / "config.yaml"
    config_block = (
        f"  config:\n    local.runtime-handler:\n{private_config}"
        if private_config
        else ""
    )
    lifecycle_block = "  lifecycle:\n%s" % lifecycle_config if lifecycle_config else ""
    path.write_text(
        "plugins:\n"
        f"  enabled: {str(enabled).lower()}\n"
        f"  plugin_list: [{plugin_name}]\n"
        "  plugin_path: ./plugins\n"
        f"{lifecycle_block}"
        f"{config_block}"
        "sources: {}\n",
        encoding="utf-8",
    )
    return path


def test_runtime_config_exposes_final_read_only_plugin_settings(tmp_path: Path):
    path = _write_config(tmp_path, enabled=False)

    config = RuntimeConfig.from_yaml(
        path,
        environ={"BUTTERBOT__PLUGINS__ENABLED": "true"},
    )

    assert config.plugin_enabled is True
    assert config.plugin_config["plugin_list"] == ("RuntimeHandlerPlugin",)
    with pytest.raises(TypeError):
        config.plugin_config["enabled"] = False  # type: ignore[index]


def test_disabled_direct_path_never_imports_plugin_package(tmp_path: Path):
    config_path = _write_config(tmp_path, enabled=False)
    code = """
import sys
from butterbot.app import BotApp
app = BotApp(config_path=sys.argv[1], cli_mode=False, logging_mode="external")
assert app.plugin_enabled is False
assert app._optional_runtime is None
assert not any(
    name == "butterbot.plugin" or name.startswith("butterbot.plugin.")
    for name in sys.modules
)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(config_path)],
        cwd=Path.cwd(),
        env=dict(os.environ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_disabled_cli_path_never_imports_plugin_package(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        code="raise AssertionError('disabled candidate must not import')\n",
    )
    config_path = _write_config(tmp_path, enabled=False)
    tmp_path.joinpath("runtime_app.py").write_text(
        "import sys\n"
        "from butterbot.app import BotApp\n"
        "\n"
        "def app(*, config, cli_mode=True):\n"
        "    assert not any(name == 'butterbot.plugin' or "
        "name.startswith('butterbot.plugin.') for name in sys.modules)\n"
        "    application = BotApp(\n"
        "        config=config, cli_mode=cli_mode, logging_mode='external'\n"
        "    )\n"
        "    def run(**kwargs):\n"
        "        assert not any(name == 'butterbot.plugin' or "
        "name.startswith('butterbot.plugin.') for name in sys.modules)\n"
        "    application.run = run\n"
        "    return application\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(Path.cwd()), str(tmp_path), environment.get("PYTHONPATH", "")]
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "butterbot.cli",
            "run",
            "-path",
            "runtime_app.app",
            "-config",
            str(config_path),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
async def test_enabled_handler_plugin_uses_application_owned_source(tmp_path: Path):
    output = tmp_path / "received.txt"
    _write_plugin(
        tmp_path / "plugins",
        code=(
            "from pathlib import Path\n"
            "from butterbot.plugin import ButterPlugin, register\n"
            "\n"
            "class RuntimeHandlerPlugin(ButterPlugin):\n"
            "    @register('runtime.events', 'runtime.message')\n"
            "    async def handle(self, event):\n"
            "        Path(str(self.settings['output'])).write_text(\n"
            "            str(event.data.value), encoding='utf-8'\n"
            "        )\n"
        ),
    )
    config_path = _write_config(
        tmp_path,
        private_config=f"      output: {output}\n",
    )
    app = BotApp(
        config_path=config_path,
        cli_mode=False,
        logging_mode="external",
    )
    app.add_source(RuntimeSource, config_key="primary")

    await app.start()
    await app.close()

    assert output.read_text(encoding="utf-8") == "ready"
    assert app.plugin_enabled is True
    assert app._optional_runtime is not None
    assert app._optional_runtime.statuses[0].state.value == "closed"


@pytest.mark.asyncio
async def test_plugin_lifecycle_wraps_source_lifecycle(tmp_path: Path):
    output = tmp_path / "lifecycle.txt"
    _write_plugin(
        tmp_path / "plugins",
        code=(
            "from pathlib import Path\n"
            "from butterbot.plugin import ButterPlugin\n"
            "\n"
            "class RuntimeHandlerPlugin(ButterPlugin):\n"
            "    async def on_start(self):\n"
            "        Path(str(self.settings['output'])).write_text('start')\n"
            "    async def on_stop(self):\n"
            "        path = Path(str(self.settings['output']))\n"
            "        path.write_text(path.read_text() + ',stop')\n"
        ),
    )
    config_path = _write_config(
        tmp_path,
        private_config=f"      output: {output}\n",
    )
    app = BotApp(config_path=config_path, cli_mode=False, logging_mode="external")

    await app.start()
    assert output.read_text() == "start"
    await app.close()

    assert output.read_text() == "start,stop"


@pytest.mark.asyncio
async def test_start_timeout_waits_for_callback_exit_before_on_stop(tmp_path: Path):
    output = tmp_path / "timeout-lifecycle.txt"
    _write_plugin(
        tmp_path / "plugins",
        code=(
            "import asyncio\n"
            "from pathlib import Path\n"
            "from butterbot.plugin import ButterPlugin\n"
            "\n"
            "class RuntimeHandlerPlugin(ButterPlugin):\n"
            "    def append(self, value):\n"
            "        path = Path(str(self.settings['output']))\n"
            "        previous = path.read_text() if path.exists() else ''\n"
            "        path.write_text(previous + value)\n"
            "    async def on_start(self):\n"
            "        self.append('start-entered,')\n"
            "        try:\n"
            "            await asyncio.Event().wait()\n"
            "        except asyncio.CancelledError:\n"
            "            self.append('cancel-observed,')\n"
            "            await asyncio.sleep(0.02)\n"
            "        self.append('start-exited,')\n"
            "    async def on_stop(self):\n"
            "        self.append('stop')\n"
        ),
    )
    config_path = _write_config(
        tmp_path,
        private_config=f"      output: {output}\n",
        lifecycle_config=(
            "    start_timeout: 0.005\n"
            "    stop_timeout: 0.1\n"
            "    cleanup_timeout: 0.1\n"
            "    drain_timeout: 0.1\n"
        ),
    )
    app = BotApp(config_path=config_path, cli_mode=False, logging_mode="external")

    with pytest.raises(PluginRegistrationError, match="starting"):
        await app.start()

    assert output.read_text() == ("start-entered,cancel-observed,start-exited,stop")
    await app.close()


@pytest.mark.asyncio
async def test_start_timeout_skips_on_stop_while_callback_refuses_cancel(
    tmp_path: Path,
):
    output = tmp_path / "stuck-lifecycle.txt"
    _write_plugin(
        tmp_path / "plugins",
        code=(
            "import asyncio\n"
            "from pathlib import Path\n"
            "from butterbot.plugin import ButterPlugin\n"
            "\n"
            "class RuntimeHandlerPlugin(ButterPlugin):\n"
            "    release = asyncio.Event()\n"
            "    def append(self, value):\n"
            "        path = Path(str(self.settings['output']))\n"
            "        previous = path.read_text() if path.exists() else ''\n"
            "        path.write_text(previous + value)\n"
            "    async def on_start(self):\n"
            "        self.append('start-entered,')\n"
            "        self.context.add_cleanup(lambda: self.append('cleanup'))\n"
            "        cancelled = False\n"
            "        while not self.release.is_set():\n"
            "            try:\n"
            "                await self.release.wait()\n"
            "            except asyncio.CancelledError:\n"
            "                if not cancelled:\n"
            "                    self.append('cancel-observed,')\n"
            "                    cancelled = True\n"
            "        self.append('start-exited')\n"
            "    async def on_stop(self):\n"
            "        self.append('stop')\n"
        ),
    )
    config_path = _write_config(
        tmp_path,
        private_config=f"      output: {output}\n",
        lifecycle_config=(
            "    start_timeout: 0.005\n"
            "    stop_timeout: 0.01\n"
            "    cleanup_timeout: 0.01\n"
            "    drain_timeout: 0.01\n"
        ),
    )
    app = BotApp(config_path=config_path, cli_mode=False, logging_mode="external")
    manager = app._optional_runtime
    assert manager is not None

    with pytest.raises(PluginRegistrationError, match="starting"):
        await app.start()

    assert output.read_text() == "start-entered,cancel-observed,"
    records = getattr(manager, "_records")
    instance = records["local.runtime-handler"].loaded.instance
    getattr(instance, "release").set()
    for _ in range(10):
        if output.read_text().endswith("start-exited"):
            break
        await asyncio.sleep(0)
    assert output.read_text() == "start-entered,cancel-observed,start-exited"
    await app.close()
    assert output.read_text() == ("start-entered,cancel-observed,start-exitedcleanup")


def test_typed_plugin_config_fails_during_application_preparation(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        code=(
            "from butterbot.plugin import ButterPlugin, PluginConfig\n"
            "\n"
            "class Settings(PluginConfig):\n"
            "    required_value: int\n"
            "\n"
            "class RuntimeHandlerPlugin(ButterPlugin[Settings]):\n"
            "    config_model = Settings\n"
        ),
    )
    config_path = _write_config(tmp_path)

    with pytest.raises(PluginRegistrationError, match="binding"):
        BotApp(config_path=config_path, logging_mode="external")


def test_enabled_plugin_discovery_error_does_not_fall_back(tmp_path: Path):
    config_path = _write_config(tmp_path)

    with pytest.raises(Exception, match="没有对应"):
        BotApp(config_path=config_path, logging_mode="external")


@pytest.mark.asyncio
async def test_source_start_failure_rolls_back_plugin_registration(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        code=(
            "from butterbot.plugin import ButterPlugin, register\n"
            "\n"
            "class RuntimeHandlerPlugin(ButterPlugin):\n"
            "    @register('runtime.events', 'runtime.message')\n"
            "    async def handle(self, event):\n"
            "        pass\n"
        ),
    )
    config_path = _write_config(tmp_path)
    app = BotApp(config_path=config_path, cli_mode=False, logging_mode="external")
    app.add_source(FailingSource)

    with pytest.raises(Exception, match="启动失败"):
        await app.start()

    assert app.bus.pending_callbacks == 0
    assert app._optional_runtime is not None
    assert app._optional_runtime.statuses[0].state.value == "failed"
    await app.close()


def test_config_and_config_path_are_mutually_exclusive(tmp_path: Path):
    config_path = _write_config(tmp_path, enabled=False)

    with pytest.raises(ValueError, match="不能同时"):
        BotApp(RuntimeConfig(), config_path=config_path)


def test_cli_mode_is_read_only_and_independent_from_plugins():
    app = BotApp(
        RuntimeConfig(plugins={"enabled": False}),
        cli_mode=False,
        logging_mode="external",
    )

    assert app.cli_mode is False
    assert app.plugin_enabled is False
    with pytest.raises(AttributeError):
        app.cli_mode = True  # type: ignore[misc]


@pytest.mark.asyncio
async def test_two_apps_do_not_share_optional_runtime_or_source_catalog(
    tmp_path: Path,
):
    _write_plugin(
        tmp_path / "plugins",
        code=(
            "from butterbot.plugin import ButterPlugin\n"
            "\n"
            "class RuntimeHandlerPlugin(ButterPlugin):\n"
            "    pass\n"
        ),
    )
    config_path = _write_config(tmp_path)
    config = RuntimeConfig.from_yaml(config_path, environ={})

    first = BotApp(config, cli_mode=False, logging_mode="external")
    second = BotApp(config, cli_mode=False, logging_mode="external")
    first.add_source(RuntimeSource, config_key="first")

    assert first._optional_runtime is not second._optional_runtime
    assert len(first.manager.source_catalog.entries) == 1
    assert second.manager.source_catalog.entries == ()
    await first.close()
    await second.close()
