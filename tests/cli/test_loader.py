"""应用入口加载测试."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from butterbot.app import BotApp
from butterbot.cli.errors import CliError
from butterbot.cli.loader import load_app, load_app_factory


def _write_module(tmp_path: Path, content: str) -> str:
    module = tmp_path / "test_cli_app.py"
    module.write_text(content, encoding="utf-8")
    return "test_cli_app"


@pytest.fixture(autouse=True)
def _clear_test_module():
    yield
    sys.modules.pop("test_cli_app", None)


def test_load_bot_app_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = _write_module(
        tmp_path,
        "from butterbot.app import BotApp, RuntimeConfig\n"
        "app = BotApp(RuntimeConfig())\n",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    app = load_app(f"{module}:app")

    assert isinstance(app, BotApp)


def test_load_zero_argument_app_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    module = _write_module(
        tmp_path,
        "from butterbot.app import BotApp, RuntimeConfig\n"
        "def create_app():\n"
        "    return BotApp(RuntimeConfig())\n",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    app = load_app(f"{module}:create_app")

    assert isinstance(app, BotApp)


def test_load_plugin_app_factory_without_calling_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    module = _write_module(
        tmp_path,
        "def create_app(*, config, source_factory_registry):\n"
        "    raise AssertionError('loader 不应调用 factory')\n",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    factory = load_app_factory(f"{module}:create_app")

    assert callable(factory)


def test_plugin_mode_rejects_constructed_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    module = _write_module(
        tmp_path,
        "from butterbot.app import BotApp, RuntimeConfig\n"
        "app = BotApp(RuntimeConfig())\n",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(CliError, match="必须是 factory"):
        load_app_factory(f"{module}:app")


@pytest.mark.parametrize(
    ("entrypoint", "message"),
    [
        ("invalid", "必须使用"),
        ("missing_module:app", "无法导入"),
        ("test_cli_app:missing", "入口不存在"),
        ("test_cli_app:nested..value", "空属性"),
    ],
)
def test_invalid_entrypoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entrypoint: str,
    message: str,
):
    _write_module(tmp_path, "value = 1\nnested = object()\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(CliError, match=message):
        load_app(entrypoint)


def test_entrypoint_must_be_bot_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    module = _write_module(tmp_path, "value = object()\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(CliError, match="没有提供 BotApp"):
        load_app(f"{module}:value")
