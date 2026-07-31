"""应用入口加载测试."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from butterbot.cli.errors import CliError
from butterbot.cli.loader import load_application, resolve_entrypoint


def _write_module(tmp_path: Path, content: str) -> str:
    module = tmp_path / "test_cli_app.py"
    module.write_text(content, encoding="utf-8")
    return "test_cli_app"


@pytest.fixture(autouse=True)
def _clear_test_module():
    yield
    sys.modules.pop("test_cli_app", None)


@pytest.mark.parametrize("entrypoint", ["test_cli_app.app", "test_cli_app:app"])
def test_load_application_without_calling_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entrypoint: str,
):
    _write_module(
        tmp_path,
        "def app(*, config, source_factory_registry):\n"
        "    raise AssertionError('loader 不应调用应用入口')\n",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    application = load_application(entrypoint)

    assert callable(application)


def test_load_application_rejects_constructed_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _write_module(tmp_path, "app = object()\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(CliError, match="必须可调用"):
        load_application("test_cli_app.app")


def test_resolve_nested_attribute_with_colon(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _write_module(
        tmp_path,
        "class Container:\n    value = 1\ncontainer = Container()\n",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    assert resolve_entrypoint("test_cli_app:container.value") == 1


@pytest.mark.parametrize(
    ("entrypoint", "message"),
    [
        ("invalid", "必须使用"),
        ("missing_module.app", "无法导入"),
        ("test_cli_app.missing", "入口不存在"),
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
        resolve_entrypoint(entrypoint)
