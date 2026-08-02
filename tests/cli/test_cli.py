"""CLI 命令和本地进程管理集成测试."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import click
import pytest
import yaml
from click.testing import CliRunner

from butterbot import __version__
from butterbot.app import BotApp
from butterbot.cli import runtime as runtime_module
from butterbot.cli.errors import CliError
from butterbot.cli.main import cli, main
from butterbot.cli.runtime import restart_application, run_application
from butterbot.cli.state import (
    RuntimeHealth,
    RuntimeState,
    StateStore,
    is_process_alive,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PID_PATTERN = re.compile(r"PID (\d+)")


@pytest.fixture(autouse=True)
def _clear_application_modules():
    yield
    for name in ("app", "positional_app", "override_app"):
        sys.modules.pop(name, None)


def test_init_creates_complete_runnable_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0

    config = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert config["plugins"]["enabled"] is True
    assert config["plugins"]["plugin_list"] == ["HelloPlugin"]
    assert config["plugins"]["plugin_path"] == "./plugins"
    assert config["sources"] == {}
    app_source = (tmp_path / "app.py").read_text(encoding="utf-8")
    assert "def app(" in app_source
    assert "cli_mode: bool = True" in app_source
    assert "BotApp(config=config, cli_mode=cli_mode)" in app_source
    plugin_root = tmp_path / "plugins" / "example.hello"
    assert 'plugin_name = "HelloPlugin"' in plugin_root.joinpath(
        "plugin.toml"
    ).read_text(encoding="utf-8")
    assert "class HelloPlugin(ButterPlugin)" in plugin_root.joinpath(
        "plugin.py"
    ).read_text(encoding="utf-8")
    assert "butterbot run" in capsys.readouterr().out

    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(BotApp, "run", lambda self, **kwargs: None)
    assert main(["run"]) == 0

    assert main(["init"]) == 1
    assert "拒绝覆盖" in capsys.readouterr().err


@pytest.mark.parametrize("config_name", ["other.yaml", "config.yaml"])
def test_run_object_entry_rejects_config_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    config_name: str,
):
    (tmp_path / "config.yaml").write_text(
        "generation: default\nplugins:\n  enabled: false\n",
        encoding="utf-8",
    )
    config_path = tmp_path / config_name
    if config_name != "config.yaml":
        config_path.write_text(
            "generation: other\nplugins:\n  enabled: false\n",
            encoding="utf-8",
        )
    (tmp_path / "app.py").write_text(
        "from butterbot.app import BotApp\napp = BotApp()\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(CliError, match="具名同步工厂"):
        main(["run", "-config", str(config_path), "--debug"])


def test_background_spawn_omits_config_when_not_specified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    (tmp_path / "config.yaml").write_text(
        "plugins:\n  enabled: false\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "butterbot.cli.runtime._spawn_background",
        lambda **kwargs: captured.update(kwargs) or 42,
    )

    assert (
        run_application(
            application=None,
            application_override=None,
            config_path=None,
            background=True,
            debug=False,
        )
        == 0
    )

    assert captured["config_path"] is None


def test_restart_spawn_omits_config_when_state_used_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    store = StateStore(tmp_path / ".butterbot" / "runtime.json")
    store.claim(
        RuntimeState.running(
            pid=os.getpid(),
            debug=False,
            working_directory=str(tmp_path),
            application_path="app.app",
            config_path=str((tmp_path / "config.yaml").resolve()),
            log_file=str(tmp_path / ".butterbot" / "butterbot.log"),
        )
    )
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "butterbot.cli.runtime._spawn_background",
        lambda **kwargs: captured.update(kwargs) or 99,
    )
    monkeypatch.setattr(
        "butterbot.cli.runtime._stop_managed_process",
        lambda store: None,
    )

    assert restart_application() == 0

    assert captured["config_path"] is None


def test_restart_spawn_passes_custom_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    store = StateStore(tmp_path / ".butterbot" / "runtime.json")
    store.claim(
        RuntimeState.running(
            pid=os.getpid(),
            debug=False,
            working_directory=str(tmp_path),
            application_path="app.app",
            config_path=str((tmp_path / "deploy.yaml").resolve()),
            log_file=str(tmp_path / ".butterbot" / "butterbot.log"),
        )
    )
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "butterbot.cli.runtime._spawn_background",
        lambda **kwargs: captured.update(kwargs) or 99,
    )
    monkeypatch.setattr(
        "butterbot.cli.runtime._stop_managed_process",
        lambda store: None,
    )

    assert restart_application() == 0

    assert captured["config_path"] == (tmp_path / "deploy.yaml").resolve()


def test_version_prints_exact_installed_version() -> None:
    result = CliRunner().invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_run_defaults_to_app_app_and_current_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    (tmp_path / "config.yaml").write_text(
        "generation: default\nplugins:\n  enabled: false\n",
        encoding="utf-8",
    )
    _write_application(tmp_path / "app.py")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(BotApp, "run", lambda self, **kwargs: None)

    assert main(["run"]) == 0

    module = sys.modules["app"]
    assert module.seen == ["default"]
    state = StateStore(tmp_path / ".butterbot" / "runtime.json").load(required=True)
    assert state is not None
    assert state.application_path == "app.app"
    assert state.config_path == str((tmp_path / "config.yaml").resolve())


def test_run_accepts_positional_application_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    config = tmp_path / "settings.yaml"
    config.write_text(
        "generation: positional\nplugins:\n  enabled: false\n",
        encoding="utf-8",
    )
    _write_application(tmp_path / "positional_app.py")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(BotApp, "run", lambda self, **kwargs: None)

    assert main(["run", "positional_app.app", "-config", str(config)]) == 0

    assert sys.modules["positional_app"].seen == ["positional"]


def test_run_path_option_overrides_positional_and_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    config = tmp_path / "custom.yaml"
    config.write_text(
        "generation: override\nplugins:\n  enabled: false\n",
        encoding="utf-8",
    )
    _write_application(tmp_path / "positional_app.py")
    _write_application(tmp_path / "override_app.py")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(BotApp, "run", lambda self, **kwargs: None)

    assert (
        main(
            [
                "run",
                "positional_app.app",
                "-path",
                "override_app.app",
                "-config",
                str(config),
            ]
        )
        == 0
    )

    assert "positional_app" not in sys.modules
    assert sys.modules["override_app"].seen == ["override"]


def test_plugin_list_and_check_report_loaded_and_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    plugin_root = tmp_path / "extensions"
    _write_plugin(plugin_root, "local.hello", "HelloPlugin")
    _write_plugin(plugin_root, "local.other", "OtherPlugin")
    config = tmp_path / "settings.yaml"
    _write_config(
        config,
        enabled=True,
        plugin_list=["HelloPlugin"],
        plugin_path="./extensions",
    )
    monkeypatch.chdir(tmp_path.parent)

    assert main(["plugin", "list", "-config", str(config)]) == 0
    output = capsys.readouterr().out
    assert "HelloPlugin" in output
    assert "OtherPlugin" in output
    assert "local.hello" in output
    assert str(plugin_root / "local.hello") in output

    assert main(["plugin", "-config", str(config), "check"]) == 0
    output = capsys.readouterr().out
    assert "HelloPlugin\tLOADED" in output
    assert "OtherPlugin\tBLOCKED: not in plugin_list" in output


def test_plugin_check_does_not_import_when_system_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    plugin_root = tmp_path / "plugins"
    _write_plugin(
        plugin_root,
        "local.disabled",
        "DisabledPlugin",
        before_class="raise AssertionError('不应导入')\n",
    )
    config = tmp_path / "config.yaml"
    _write_config(
        config,
        enabled=False,
        plugin_list=["DisabledPlugin"],
        plugin_path="./plugins",
    )
    monkeypatch.chdir(tmp_path)

    assert main(["plugin", "check"]) == 0
    assert "BLOCKED: plugins.enabled=false" in capsys.readouterr().out


def test_plugin_check_isolates_candidate_process_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    plugin_root = tmp_path / "plugins"
    _write_plugin(
        plugin_root,
        "local.isolated",
        "IsolatedPlugin",
        before_class=(
            "import os\nos.environ['BUTTERBOT_CHECK_CANDIDATE_LEAK'] = 'candidate'\n"
        ),
    )
    _write_config(
        tmp_path / "config.yaml",
        enabled=True,
        plugin_list=["IsolatedPlugin"],
        plugin_path="./plugins",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BUTTERBOT_CHECK_CANDIDATE_LEAK", raising=False)

    assert main(["plugin", "check"]) == 0

    assert "IsolatedPlugin\tLOADED" in capsys.readouterr().out
    assert "BUTTERBOT_CHECK_CANDIDATE_LEAK" not in os.environ


def test_plugin_check_reports_missing_selected_plugin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    _write_config(
        tmp_path / "config.yaml",
        enabled=True,
        plugin_list=["MissingPlugin"],
        plugin_path="./plugins",
    )
    monkeypatch.chdir(tmp_path)

    assert main(["plugin", "check"]) == 1
    captured = capsys.readouterr()
    assert "MissingPlugin\tMISSING" in captured.out
    assert "发现错误" in captured.err


def test_plugin_command_fallback_writes_all_plugin_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    plugin_root = tmp_path / "plugins"
    _write_plugin(plugin_root, "local.hello", "HelloPlugin")
    config = tmp_path / "settings.yaml"
    data = {
        "plugins": {
            "enabled": False,
            "plugin_list": ["MissingPlugin"],
            "plugin_path": "./plugins",
            "config": {"local.keep": {"value": 1}},
        },
        "sources": {"keep": {"source_name": "demo"}},
    }
    config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)

    result = CliRunner().invoke(
        cli,
        ["plugin", "-config", str(config)],
        input="y\n\n1\ny\n1\n2\n3\n4\ny\n",
    )

    assert result.exit_code == 0, result.output
    written = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert written["plugins"]["enabled"] is True
    assert written["plugins"]["plugin_list"] == ["HelloPlugin"]
    assert written["plugins"]["plugin_path"] == "./plugins"
    assert written["plugins"]["lifecycle"] == {
        "start_timeout": 1.0,
        "stop_timeout": 2.0,
        "cleanup_timeout": 3.0,
        "drain_timeout": 4.0,
    }
    assert written["plugins"]["config"] == {"local.keep": {"value": 1}}
    assert written["sources"] == {"keep": {"source_name": "demo"}}
    assert str(plugin_root / "local.hello") in result.output


def test_plugin_command_uses_full_screen_key_navigation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    plugin_root = tmp_path / "plugins"
    _write_plugin(plugin_root, "local.hello", "HelloPlugin")
    config = tmp_path / "config.yaml"
    _write_config(
        config,
        enabled=False,
        plugin_list=["MissingPlugin"],
        plugin_path="./plugins",
    )
    keys = iter(["enter", "down", "down", "down", "enter", "down", "enter", "q"])
    monkeypatch.setattr(
        "butterbot.cli.configurator.is_interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "butterbot.cli.terminal.is_interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "butterbot.cli.configurator.read_key",
        lambda: next(keys),
    )
    monkeypatch.chdir(tmp_path)

    assert main(["plugin"]) == 0

    written = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert written["plugins"]["enabled"] is True
    assert written["plugins"]["plugin_list"] == ["HelloPlugin"]
    output = capsys.readouterr().out
    assert "\x1b[?1049h" in output
    assert "\x1b[?1049l" in output
    assert str(plugin_root / "local.hello") in output


def test_config_command_fallback_only_changes_plugin_switch(
    tmp_path: Path,
):
    config = tmp_path / "project.yaml"
    original = {
        "plugins": {
            "enabled": False,
            "plugin_list": ["KeepPlugin"],
            "plugin_path": "./custom",
        },
        "sources": {"keep": {"source_name": "demo"}},
    }
    config.write_text(yaml.safe_dump(original, sort_keys=False), encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        ["config", "-config", str(config)],
        input="y\ny\n",
    )

    assert result.exit_code == 0, result.output
    written = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert written["plugins"] == {
        "enabled": True,
        "plugin_list": ["KeepPlugin"],
        "plugin_path": "./custom",
    }
    assert written["sources"] == original["sources"]
    assert "Sources: 自动发现" in result.output


def test_click_command_tree_and_help():
    assert isinstance(cli, click.Group)

    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "Commands:" in result.output
    assert "plugin" in result.output
    assert "run" in result.output


def test_removed_commands_are_rejected():
    assert main(["check"]) == 2
    assert main(["close"]) == 2
    assert main(["plugins"]) == 2


def test_status_without_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["status"])

    assert exit_code == 3
    assert "未登记" in capsys.readouterr().out


def test_status_reports_aggregated_degraded_health(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    store = StateStore(tmp_path / ".butterbot" / "runtime.json")
    state = RuntimeState.running(
        pid=os.getpid(),
        debug=False,
        working_directory=str(tmp_path),
        application_path="app.app",
        config_path=str(tmp_path / "config.yaml"),
        log_file=str(tmp_path / ".butterbot" / "butterbot.log"),
    )
    store.claim(state)
    store.update_health(
        state.token,
        RuntimeHealth(
            state="degraded",
            observed_at=time.time(),
            source_total=2,
            source_ready=1,
            source_degraded=1,
            plugin_total=1,
            plugin_unhealthy=1,
            failure_types=("ConnectionError", "TimeoutError"),
        ),
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(["status"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "运行降级" in output
    assert "Source 1/2 ready" in output
    assert "Plugin 0/1 healthy" in output
    assert "ConnectionError" in output


def test_debug_preserves_configuration_traceback():
    with pytest.raises(FileNotFoundError):
        main(["run", "invalid", "--debug"])


def test_non_debug_reports_cli_error(capsys: pytest.CaptureFixture[str]):
    exit_code = main(["run", "invalid"])

    assert exit_code == 1
    assert "配置无效:" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform == "win32", reason="依赖 POSIX SIGTERM 进程管理")
def test_background_full_restart_and_stop(tmp_path: Path):
    module = tmp_path / "managed_app.py"
    module.write_text(
        "from pathlib import Path\n"
        "from butterbot.app import BotApp\n"
        "def app(*, config, cli_mode=True):\n"
        "    with Path('starts.log').open('a', encoding='utf-8') as output:\n"
        "        output.write(config.get_config('generation') + '\\n')\n"
        "    return BotApp(config=config, cli_mode=cli_mode)\n",
        encoding="utf-8",
    )
    config = tmp_path / "runtime.yaml"
    config.write_text(
        "generation: first\nplugins:\n  enabled: false\n",
        encoding="utf-8",
    )
    state_file = tmp_path / ".butterbot" / "runtime.json"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(PROJECT_ROOT), str(tmp_path), environment.get("PYTHONPATH", "")]
    )

    def cli(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "butterbot.cli", *arguments],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    try:
        started = cli(
            "run",
            "managed_app.app",
            "-config",
            str(config),
            "--background",
            "--debug",
        )
        assert started.returncode == 0, started.stderr
        first_pid = _extract_pid(started.stdout)

        status = cli("status")
        assert status.returncode == 0, status.stderr
        assert str(first_pid) in status.stdout

        state = StateStore(state_file).load(required=True)
        assert state is not None
        assert state.debug
        assert state.application_path == "managed_app.app"
        assert state.config_path == str(config.resolve())

        duplicate = cli("run", "--background")
        assert duplicate.returncode == 1
        assert "正在运行" in duplicate.stderr

        config.write_text(
            "generation: second\nplugins:\n  enabled: false\n",
            encoding="utf-8",
        )
        restarted = cli("restart")
        assert restarted.returncode == 0, restarted.stderr
        second_pid = _extract_pid(restarted.stdout)
        assert second_pid != first_pid
        _wait_until_process_exits(first_pid)

        assert (tmp_path / "starts.log").read_text(encoding="utf-8").splitlines() == [
            "first",
            "second",
        ]

        stopped = cli("stop")
        assert stopped.returncode == 0, stopped.stderr
        assert "已停止" in stopped.stdout
        _wait_until_process_exits(second_pid)

        status = cli("status")
        assert status.returncode == 3
        assert "已停止" in status.stdout

        config.write_text(
            "generation: third\nplugins:\n  enabled: false\n",
            encoding="utf-8",
        )
        restarted_from_stopped = cli("restart")
        assert restarted_from_stopped.returncode == 0, restarted_from_stopped.stderr
        third_pid = _extract_pid(restarted_from_stopped.stdout)
        assert third_pid not in (first_pid, second_pid)
        assert (tmp_path / "starts.log").read_text(encoding="utf-8").splitlines() == [
            "first",
            "second",
            "third",
        ]

        stopped_again = cli("stop")
        assert stopped_again.returncode == 0, stopped_again.stderr
        assert "已停止" in stopped_again.stdout
        _wait_until_process_exits(third_pid)
    finally:
        state = StateStore(state_file).refresh()
        if state is not None and is_process_alive(state) and state.pid is not None:
            os.kill(state.pid, signal.SIGTERM)
            _wait_until_process_exits(state.pid)


@pytest.mark.skipif(sys.platform == "win32", reason="依赖 POSIX 进程组信号")
def test_background_start_timeout_kills_and_reaps_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """导入阶段卡死且忽略 SIGTERM 时，启动方必须升级 SIGKILL 并 wait."""
    (tmp_path / "slow_app.py").write_text(
        "import os\n"
        "import signal\n"
        "import time\n"
        "from pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "Path('slow.pid').write_text(str(os.getpid()), encoding='utf-8')\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        "plugins:\n  enabled: false\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(
            [str(PROJECT_ROOT), str(tmp_path), os.environ.get("PYTHONPATH", "")]
        ),
    )
    monkeypatch.setattr(runtime_module, "_BACKGROUND_START_TIMEOUT", 1.0)
    monkeypatch.setattr(runtime_module, "_BACKGROUND_CLEANUP_TIMEOUT", 0.1)

    with pytest.raises(CliError, match="登记状态超时"):
        runtime_module._spawn_background(
            application_path="slow_app.app",
            config_path=None,
            debug=False,
            working_directory=tmp_path,
        )

    pid = int((tmp_path / "slow.pid").read_text(encoding="utf-8"))
    _wait_until_process_exits(pid)


def _write_application(path: Path) -> None:
    path.write_text(
        "from butterbot.app import BotApp\n"
        "seen = []\n"
        "def app(*, config, cli_mode=True):\n"
        "    seen.append(config.get_config('generation'))\n"
        "    return BotApp(config=config, cli_mode=cli_mode)\n",
        encoding="utf-8",
    )


def _write_plugin(
    root: Path,
    plugin_id: str,
    plugin_name: str,
    *,
    before_class: str = "",
) -> None:
    directory = root / plugin_id
    directory.mkdir(parents=True)
    directory.joinpath("plugin.toml").write_text(
        "schema_version = 2\n"
        f'plugin_name = "{plugin_name}"\n'
        'version = "0.1.0"\n'
        'requires_core = ">=3.1.0b1,<3.2"\n'
        'entry = "plugin.py"\n'
        "requires_plugins = []\n"
        "requires_distributions = []\n",
        encoding="utf-8",
    )
    directory.joinpath("plugin.py").write_text(
        "from butterbot.plugin import ButterPlugin\n"
        f"{before_class}"
        f"class {plugin_name}(ButterPlugin):\n"
        "    pass\n",
        encoding="utf-8",
    )


def _write_config(
    path: Path,
    *,
    enabled: bool,
    plugin_list: list[str],
    plugin_path: str,
) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "plugins": {
                    "enabled": enabled,
                    "plugin_list": plugin_list,
                    "plugin_path": plugin_path,
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _extract_pid(output: str) -> int:
    match = PID_PATTERN.search(output)
    assert match is not None, output
    return int(match.group(1))


def _wait_until_process_exits(pid: int) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    pytest.fail("进程 %s 未完全退出" % pid)
