"""插件公共 API 和依赖边界回归测试."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import butterbot.core as core
import butterbot.core.source as core_source

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = PROJECT_ROOT / "butterbot" / "core"
HANDLER_PLUGIN_FILES = (
    PROJECT_ROOT / "examples" / "plugins" / "manager_example" / "plugin.py",
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "local_plugins"
    / "handler_only"
    / "plugin.py",
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "local_plugins"
    / "hybrid_handler"
    / "plugin.py",
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "plugins"
    / "handler_only"
    / "src"
    / "contract_handler"
    / "__init__.py",
)


def test_app_and_plugin_public_api_import_in_fresh_process() -> None:
    """两种导入顺序都不能触发 plugin bootstrap 循环依赖."""
    plugin_import = "\n".join(
        (
            "from butterbot.plugin import (",
            "    Event, LocalPlugin, PluginBootstrap, PluginRegistrar,",
            "    SourceRef, SubscriptionSpec,",
            ")",
        )
    )
    for code in (
        "from butterbot.app import BotApp\n" + plugin_import,
        plugin_import + "\nfrom butterbot.app import BotApp",
    ):
        subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )


def test_source_ref_is_not_exported_from_core() -> None:
    assert not hasattr(core, "SourceRef")
    assert not hasattr(core_source, "SourceRef")


def test_core_does_not_import_plugin_package() -> None:
    for path in CORE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(
            name == "butterbot.plugin" or name.startswith("butterbot.plugin.")
            for name in imported_modules
        ), path


def test_handler_only_plugins_do_not_import_core() -> None:
    for path in HANDLER_PLUGIN_FILES:
        assert "butterbot.core" not in path.read_text(encoding="utf-8"), path
