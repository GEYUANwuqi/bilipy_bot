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
PLUGIN_ROOT = PROJECT_ROOT / "butterbot" / "plugin"
HANDLER_PLUGIN_FILES = (
    PROJECT_ROOT / "examples" / "plugins" / "example.bilibili-manager" / "plugin.py",
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "local_plugins"
    / "local.contract.handler"
    / "plugin.py",
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "local_plugins"
    / "local.contract.hybrid-handler"
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
            "from butterbot.core import Event",
            "from butterbot.plugin import (",
            "    ButterPlugin, PluginBootstrap, PluginConfig, PluginContext,",
            "    PluginRegistrar, PluginScope, SourceRef, SubscriptionSpec, register,",
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


def test_obsolete_plugin_base_names_are_not_exported() -> None:
    import butterbot.plugin as plugin

    assert not hasattr(plugin, "LocalPlugin")
    assert not hasattr(plugin, "PluginBase")
    assert not hasattr(plugin.ButterPlugin, "register_config")
    assert not hasattr(plugin.ButterPlugin, "register")
    assert not hasattr(plugin, "start")
    assert not hasattr(plugin, "stop")
    assert hasattr(plugin.ButterPlugin, "on_start")
    assert hasattr(plugin.ButterPlugin, "on_stop")


def test_core_types_are_not_exported_from_plugin() -> None:
    import butterbot.plugin as plugin

    for name in ("AndFilter", "BaseFilter", "BaseType", "Event", "OrFilter"):
        assert not hasattr(plugin, name)


def test_plugin_package_is_grouped_by_responsibility() -> None:
    root_modules = {path.name for path in PLUGIN_ROOT.glob("*.py")}

    assert root_modules == {"__init__.py", "errors.py"}
    assert {
        "contracts",
        "discovery",
        "runtime",
    } <= {path.name for path in PLUGIN_ROOT.iterdir() if path.is_dir()}


def test_descriptor_module_has_one_public_concept() -> None:
    from butterbot.plugin.contracts import descriptor

    assert descriptor.__all__ == ["PluginDescriptor"]


def _module_directory(module_name: str) -> Path | None:
    module_path = PROJECT_ROOT.joinpath(*module_name.split("."))
    file_path = module_path.with_suffix(".py")
    if file_path.is_file():
        return file_path.parent
    if module_path.joinpath("__init__.py").is_file():
        return module_path
    return None


def test_plugin_internal_imports_follow_directory_boundaries() -> None:
    """同目录使用单点相对导入，跨目录使用完整绝对导入."""
    for path in PLUGIN_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                assert node.level == 1, path
                assert node.module is not None, path
                target_dir = _module_directory(
                    ".".join(
                        (
                            *path.parent.relative_to(PROJECT_ROOT).parts,
                            node.module,
                        )
                    )
                )
                assert target_dir == path.parent, (path, node.module)
                continue

            module_names: tuple[str, ...] = ()
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                module_names = (node.module,)
            elif isinstance(node, ast.Import):
                module_names = tuple(alias.name for alias in node.names)
            for module_name in module_names:
                if module_name == "butterbot.plugin" or module_name.startswith(
                    "butterbot.plugin."
                ):
                    target_dir = _module_directory(module_name)
                    assert target_dir is not None, (path, module_name)
                    assert target_dir != path.parent, (path, module_name)


def test_lazy_plugin_exports_use_absolute_module_paths() -> None:
    import butterbot.plugin as plugin

    assert all(
        module_name.startswith("butterbot.plugin.")
        for module_name, _ in plugin._LAZY_EXPORTS.values()
    )


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


def test_handler_plugins_import_core_types_from_core() -> None:
    for path in HANDLER_PLUGIN_FILES:
        source = path.read_text(encoding="utf-8")
        assert "butterbot.core" in source, path
        assert "    Event," not in source, path
        assert "PluginRegistrar" not in source, path
        assert "SourceRef" not in source, path
        assert "SubscriptionSpec" not in source, path
