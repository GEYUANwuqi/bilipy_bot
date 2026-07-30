"""CLI 命令和本地进程管理集成测试."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from butterbot.cli.errors import CliError
from butterbot.cli.main import main
from butterbot.cli.state import StateStore, is_process_alive

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PID_PATTERN = re.compile(r"PID (\d+)")


def test_check_config_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    (tmp_path / "config.yaml").write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["check"])

    assert exit_code == 0
    assert "配置有效" in capsys.readouterr().out


def test_check_config_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    (tmp_path / "config.yaml").write_text("sources: []\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["check"])

    assert exit_code == 1
    assert "配置无效" in capsys.readouterr().err


def test_check_config_with_plugin_app_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    (tmp_path / "config.yaml").write_text("{}\n", encoding="utf-8")
    (tmp_path / "checked_app.py").write_text(
        "from butterbot.app import BotApp\n"
        "def create_app(*, config, source_factory_registry):\n"
        "    return BotApp(\n"
        "        config,\n"
        "        source_factory_registry=source_factory_registry,\n"
        "    )\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    exit_code = main(["check", "checked_app:create_app"])

    assert exit_code == 0
    assert "配置有效" in capsys.readouterr().out


def test_plugins_init_list_and_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.chdir(tmp_path)

    assert main(["plugins", "init", "local.created"]) == 0
    plugin_root = tmp_path / "plugins" / "local.created"
    assert plugin_root.joinpath("plugin.toml").is_file()
    assert plugin_root.joinpath("plugin.py").is_file()
    assert 'entry = "plugin.py"' in plugin_root.joinpath("plugin.toml").read_text(
        encoding="utf-8"
    )
    assert "ButterPlugin" in plugin_root.joinpath("plugin.py").read_text(
        encoding="utf-8"
    )
    assert "create_plugin" not in plugin_root.joinpath("plugin.py").read_text(
        encoding="utf-8"
    )
    assert main(["plugins", "init", "local.created"]) == 1
    assert "拒绝覆盖" in capsys.readouterr().err

    (tmp_path / "config.yaml").write_text(
        "plugins:\n  enabled: [local.created]\n  local: {}\n",
        encoding="utf-8",
    )
    assert main(["plugins", "list"]) == 0
    output = capsys.readouterr().out
    assert "local.created" in output
    assert "directory" in output
    assert "yes" in output

    assert main(["plugins", "check"]) == 0
    assert "配置有效" in capsys.readouterr().out


def test_status_without_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["status"])

    assert exit_code == 3
    assert "未登记" in capsys.readouterr().out


def test_debug_preserves_cli_traceback():
    with pytest.raises(CliError):
        main(["run", "invalid", "--debug"])


def test_non_debug_reports_cli_error(capsys: pytest.CaptureFixture[str]):
    exit_code = main(["run", "invalid"])

    assert exit_code == 1
    assert "错误:" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform == "win32", reason="依赖 POSIX SIGTERM 进程管理")
def test_background_full_restart_and_close(tmp_path: Path):
    module = tmp_path / "managed_app.py"
    module.write_text(
        "from pathlib import Path\n"
        "from butterbot.app import BotApp, RuntimeConfig\n"
        "config = RuntimeConfig.from_yaml()\n"
        "with Path('starts.log').open('a', encoding='utf-8') as output:\n"
        "    output.write(config.get_config('generation') + '\\n')\n"
        "app = BotApp(config)\n",
        encoding="utf-8",
    )
    config = tmp_path / "config.yaml"
    config.write_text("generation: first\n", encoding="utf-8")
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
        started = cli("run", "managed_app:app", "--background", "--debug")
        assert started.returncode == 0, started.stderr
        first_pid = _extract_pid(started.stdout)

        status = cli("status")
        assert status.returncode == 0, status.stderr
        assert str(first_pid) in status.stdout

        state = StateStore(state_file).load(required=True)
        assert state is not None
        assert state.debug

        paused = cli("stop")
        assert paused.returncode == 0, paused.stderr
        _wait_until_process_paused(first_pid)

        status = cli("status")
        assert status.returncode == 0
        assert "已暂停" in status.stdout

        resumed = cli("run", "managed_app:app", "--background")
        assert resumed.returncode == 0, resumed.stderr
        assert "已恢复原进程" in resumed.stdout
        assert "未创建新实例" in resumed.stdout
        assert _extract_pid(resumed.stdout) == first_pid
        assert (tmp_path / "starts.log").read_text(encoding="utf-8").splitlines() == [
            "first"
        ]

        duplicate = cli("run", "managed_app:app", "--background")
        assert duplicate.returncode == 1
        assert "正在运行" in duplicate.stderr

        paused_again = cli("stop")
        assert paused_again.returncode == 0, paused_again.stderr
        _wait_until_process_paused(first_pid)

        config.write_text("generation: second\n", encoding="utf-8")
        restarted = cli("restart")
        assert restarted.returncode == 0, restarted.stderr
        second_pid = _extract_pid(restarted.stdout)
        assert second_pid != first_pid
        _wait_until_process_exits(first_pid)

        assert (tmp_path / "starts.log").read_text(encoding="utf-8").splitlines() == [
            "first",
            "second",
        ]

        closed = cli("close")
        assert closed.returncode == 0, closed.stderr
        _wait_until_process_exits(second_pid)

        status = cli("status")
        assert status.returncode == 3
        assert "已停止" in status.stdout

        config.write_text("generation: third\n", encoding="utf-8")
        restarted_from_stopped = cli("restart")
        assert restarted_from_stopped.returncode == 0, restarted_from_stopped.stderr
        third_pid = _extract_pid(restarted_from_stopped.stdout)
        assert third_pid not in (first_pid, second_pid)
        assert (tmp_path / "starts.log").read_text(encoding="utf-8").splitlines() == [
            "first",
            "second",
            "third",
        ]

        paused_third = cli("stop")
        assert paused_third.returncode == 0, paused_third.stderr
        _wait_until_process_paused(third_pid)

        closed_again = cli("close")
        assert closed_again.returncode == 0, closed_again.stderr
        _wait_until_process_exits(third_pid)
    finally:
        state = StateStore(state_file).refresh()
        if state is not None and is_process_alive(state) and state.pid is not None:
            if state.status == "paused":
                os.kill(state.pid, signal.SIGCONT)
            os.kill(state.pid, signal.SIGTERM)
            _wait_until_process_exits(state.pid)


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


def _wait_until_process_paused(pid: int) -> None:
    deadline = time.monotonic() + 5
    stat_path = Path("/proc") / str(pid) / "stat"
    while time.monotonic() < deadline:
        try:
            stat = stat_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            pytest.fail("进程 %s 在暂停前退出" % pid)
        closing_parenthesis = stat.rfind(")")
        if closing_parenthesis >= 0:
            fields = stat[closing_parenthesis + 2 :].split()
            if fields and fields[0] in ("T", "t"):
                return
        time.sleep(0.05)
    pytest.fail("进程 %s 未进入暂停状态" % pid)
