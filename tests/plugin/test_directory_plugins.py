"""本地目录插件测试."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from butterbot.plugin import (
    ButterPlugin,
    PluginDependencyError,
    PluginDescriptor,
    PluginDiscoveryError,
)
from butterbot.plugin.discovery.catalog import PluginCatalog
from butterbot.plugin.discovery.settings import LocalPluginSettings

CORE_VERSION = "3.1.0.dev2"


@dataclass
class FakeEntryPoint:
    name: str
    target: Any
    value: str = "tests.fake:Plugin"
    loads: int = 0

    def load(self) -> Any:
        self.loads += 1
        return self.target


def write_plugin(
    root: Path,
    plugin_id: str,
    *,
    plugin_name: str | None = None,
    requires_plugins: tuple[str, ...] = (),
    requires_distributions: tuple[str, ...] = (),
    code: str | None = None,
) -> Path:
    plugin_root = root / plugin_id
    plugin_root.mkdir(parents=True)
    resolved_plugin_name = plugin_name or "Hooks"
    plugin_root.joinpath("plugin.toml").write_text(
        "schema_version = 2\n"
        f'plugin_name = "{resolved_plugin_name}"\n'
        'version = "0.1.0"\n'
        'requires_core = ">=3.1.0.dev2,<4"\n'
        'entry = "plugin.py"\n'
        "requires_plugins = [%s]\n"
        "requires_distributions = [%s]\n"
        % (
            ", ".join('"%s"' % item for item in requires_plugins),
            ", ".join('"%s"' % item for item in requires_distributions),
        ),
        encoding="utf-8",
    )
    plugin_root.joinpath("plugin.py").write_text(
        code
        or (
            "from butterbot.plugin import ButterPlugin\n"
            "\n"
            "class Hooks(ButterPlugin):\n"
            "    pass\n"
        ),
        encoding="utf-8",
    )
    return plugin_root


def local_settings() -> LocalPluginSettings:
    return LocalPluginSettings(path="./plugins")


def test_disabled_local_plugin_is_indexed_without_import(tmp_path: Path):
    plugin_root = tmp_path / "plugins"
    write_plugin(
        plugin_root,
        "local.disabled",
        code="raise RuntimeError('disabled plugin must not import')\n",
    )

    catalog = PluginCatalog.discover(
        [],
        entry_points=[],
        local=local_settings(),
        config_root=tmp_path,
        core_version=CORE_VERSION,
    )

    assert catalog.plugin_ids == ()
    assert tuple(candidate.plugin_id for candidate in catalog.candidates) == (
        "local.disabled",
    )
    descriptor = catalog.candidates[0].descriptor
    assert descriptor is not None
    assert catalog.candidates[0].plugin_name == "Hooks"


def test_local_plugin_id_comes_from_directory_and_name_matches_class(
    tmp_path: Path,
):
    write_plugin(
        tmp_path / "plugins",
        "local.display-name",
        plugin_name="LocalDisplayPlugin",
        code=(
            "from butterbot.plugin import ButterPlugin\n"
            "\n"
            "class LocalDisplayPlugin(ButterPlugin):\n"
            "    pass\n"
        ),
    )

    candidate = PluginCatalog.index_candidates(
        entry_points=[],
        local=local_settings(),
        config_root=tmp_path,
    )[0]

    assert candidate.plugin_id == "local.display-name"
    assert candidate.descriptor is not None
    assert candidate.plugin_name == "LocalDisplayPlugin"
    assert candidate.descriptor.provides == ()

    catalog = PluginCatalog.discover(
        ["LocalDisplayPlugin"],
        entry_points=[],
        local=local_settings(),
        config_root=tmp_path,
        core_version=CORE_VERSION,
    )
    assert catalog.selected_names == ("LocalDisplayPlugin",)
    assert catalog.plugin_ids == ("local.display-name",)


def test_local_plugin_name_must_match_loaded_class(tmp_path: Path):
    write_plugin(
        tmp_path / "plugins",
        "local.name-mismatch",
        plugin_name="DeclaredPlugin",
        code=(
            "from butterbot.plugin import ButterPlugin\n"
            "\n"
            "class ActualPlugin(ButterPlugin):\n"
            "    pass\n"
        ),
    )

    with pytest.raises(PluginDiscoveryError, match="实现类名 'ActualPlugin'"):
        PluginCatalog.discover(
            ["DeclaredPlugin"],
            entry_points=[],
            local=local_settings(),
            config_root=tmp_path,
            core_version=CORE_VERSION,
        )


@pytest.mark.parametrize("field", ("enabled", "plugin_id", "provides"))
def test_removed_local_manifest_fields_are_rejected(
    tmp_path: Path,
    field: str,
):
    plugin_root = write_plugin(tmp_path / "plugins", "local.removed-field")
    manifest = plugin_root / "plugin.toml"
    suffix = {
        "enabled": "enabled = true\n",
        "plugin_id": 'plugin_id = "local.alias"\n',
        "provides": 'provides = ["local.capability"]\n',
    }[field]
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + suffix,
        encoding="utf-8",
    )

    with pytest.raises(PluginDiscoveryError, match="未知字段"):
        PluginCatalog.index_candidates(
            entry_points=[],
            local=local_settings(),
            config_root=tmp_path,
        )


def test_local_plugin_directory_must_be_a_valid_plugin_id(tmp_path: Path):
    write_plugin(tmp_path / "plugins", "Invalid Folder", plugin_name="Invalid")

    with pytest.raises(PluginDiscoveryError, match="plugin_id"):
        PluginCatalog.index_candidates(
            entry_points=[],
            local=local_settings(),
            config_root=tmp_path,
        )


def test_invalid_disabled_manifest_still_fails_check(tmp_path: Path):
    plugin_root = tmp_path / "plugins" / "broken"
    plugin_root.mkdir(parents=True)
    plugin_root.joinpath("plugin.toml").write_text(
        'plugin_name = "Broken"\n',
        encoding="utf-8",
    )

    with pytest.raises(PluginDiscoveryError, match="缺少字段"):
        PluginCatalog.discover(
            [],
            entry_points=[],
            local=local_settings(),
            config_root=tmp_path,
            core_version=CORE_VERSION,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda text: text + "unknown_field = true\n",
            "未知字段",
        ),
        (
            lambda text: text.replace(
                'entry = "plugin.py"',
                'entry = "../outside.py"',
            ),
            "根目录直接 Python 文件",
        ),
        (
            lambda text: text.replace("schema_version = 2", "schema_version = 1"),
            "descriptor 无效",
        ),
        (
            lambda text: text.replace(
                'plugin_name = "Hooks"',
                'plugin_name = ""',
            ),
            "plugin_name",
        ),
        (
            lambda text: text.replace(
                "requires_distributions = []",
                'requires_distributions = ["not a valid requirement !!!"]',
            ),
            "无效 Python distribution",
        ),
    ],
)
def test_manifest_schema_and_entry_are_strict(
    tmp_path: Path,
    mutation,
    message: str,
):
    plugin_root = write_plugin(tmp_path / "plugins", "local.strict")
    manifest = plugin_root / "plugin.toml"
    manifest.write_text(
        mutation(manifest.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    with pytest.raises(PluginDiscoveryError, match=message):
        PluginCatalog.index_candidates(
            entry_points=[],
            local=local_settings(),
            config_root=tmp_path,
        )


def test_symlink_entry_is_rejected(tmp_path: Path):
    plugin_root = write_plugin(tmp_path / "plugins", "local.symlink")
    entry = plugin_root / "plugin.py"
    external = tmp_path / "external.py"
    external.write_text("class Plugin: ...\n", encoding="utf-8")
    entry.unlink()
    entry.symlink_to(external)

    with pytest.raises(PluginDiscoveryError, match="符号链接"):
        PluginCatalog.index_candidates(
            entry_points=[],
            local=local_settings(),
            config_root=tmp_path,
        )


def test_missing_local_root_has_no_candidates(tmp_path: Path):
    catalog = PluginCatalog.discover(
        [],
        entry_points=[],
        local=local_settings(),
        config_root=tmp_path,
        core_version=CORE_VERSION,
    )

    assert catalog.candidates == ()


def test_plugin_list_loads_local_plugin_without_sys_path_changes(tmp_path: Path):
    plugin_root = tmp_path / "plugins"
    local = write_plugin(
        plugin_root,
        "local.relative",
        code=(
            "from butterbot.plugin import ButterPlugin\n"
            "from .helpers import VALUE\n"
            "\n"
            "class Hooks(ButterPlugin):\n"
            "    value = VALUE\n"
        ),
    )
    local.joinpath("helpers.py").write_text(
        "VALUE = 'workspace-one'\n", encoding="utf-8"
    )
    original_path = tuple(sys.path)

    catalog = PluginCatalog.discover(
        ["Hooks"],
        entry_points=[],
        local=local_settings(),
        config_root=tmp_path,
        core_version=CORE_VERSION,
    )

    loaded = catalog.get("local.relative")
    assert loaded is not None
    assert getattr(loaded.instance, "value") == "workspace-one"
    assert loaded.origin.kind == "directory"
    assert loaded.origin.fingerprint is not None
    assert tuple(sys.path) == original_path


@pytest.mark.parametrize(
    ("code", "found"),
    [
        (
            "VALUE = 1\n",
            "找到: 0",
        ),
        (
            "from butterbot.plugin import ButterPlugin\n"
            "class One(ButterPlugin):\n"
            "    pass\n"
            "class Two(ButterPlugin):\n"
            "    pass\n",
            "One, Two",
        ),
    ],
)
def test_entry_module_must_define_exactly_one_local_plugin_class(
    tmp_path: Path,
    code: str,
    found: str,
):
    write_plugin(
        tmp_path / "plugins",
        "local.ambiguous",
        code=code,
    )

    with pytest.raises(PluginDiscoveryError, match=found):
        PluginCatalog.discover(
            ["Hooks"],
            entry_points=[],
            local=local_settings(),
            config_root=tmp_path,
            core_version=CORE_VERSION,
        )


def test_fingerprint_changes_when_helper_code_changes(tmp_path: Path):
    plugin_root = write_plugin(tmp_path / "plugins", "local.fingerprint")
    helper = plugin_root / "helpers.py"
    helper.write_text("VALUE = 1\n", encoding="utf-8")
    first = PluginCatalog.index_candidates(
        entry_points=[],
        local=local_settings(),
        config_root=tmp_path,
    )[0].origin.fingerprint

    helper.write_text("VALUE = 2\n", encoding="utf-8")
    second = PluginCatalog.index_candidates(
        entry_points=[],
        local=local_settings(),
        config_root=tmp_path,
    )[0].origin.fingerprint

    assert first != second


def test_same_folder_and_module_names_are_isolated_across_workspaces(
    tmp_path: Path,
):
    catalogs = []
    for index in (1, 2):
        workspace = tmp_path / ("workspace-%s" % index)
        local = write_plugin(
            workspace / "plugins",
            "same",
            code=(
                "from butterbot.plugin import ButterPlugin\n"
                "from .helpers import VALUE\n"
                "\n"
                "class Hooks(ButterPlugin):\n"
                "    value = VALUE\n"
            ),
        )
        local.joinpath("helpers.py").write_text(
            "VALUE = 'workspace-%s'\n" % index,
            encoding="utf-8",
        )
        catalogs.append(
            PluginCatalog.discover(
                ["Hooks"],
                entry_points=[],
                local=local_settings(),
                config_root=workspace,
                core_version=CORE_VERSION,
            )
        )

    assert getattr(catalogs[0].plugins[0].instance, "value") == "workspace-1"
    assert getattr(catalogs[1].plugins[0].instance, "value") == "workspace-2"


def test_import_failure_removes_only_failed_synthetic_namespace(tmp_path: Path):
    write_plugin(
        tmp_path / "plugins",
        "local.failure",
        code="from .missing import value\n",
    )
    before = {name for name in sys.modules if name.startswith("_butterbot_local.")}

    with pytest.raises(PluginDiscoveryError, match="导入本地插件"):
        PluginCatalog.discover(
            ["Hooks"],
            entry_points=[],
            local=local_settings(),
            config_root=tmp_path,
            core_version=CORE_VERSION,
        )

    after = {name for name in sys.modules if name.startswith("_butterbot_local.")}
    assert after == before


def test_distribution_requirements_fail_before_import(tmp_path: Path):
    marker = tmp_path / "imported"
    write_plugin(
        tmp_path / "plugins",
        "local.missing-dependency",
        requires_distributions=("butterbot-definitely-missing-contract>=1",),
        code=f"from pathlib import Path\nPath({str(marker)!r}).touch()\n",
    )

    with pytest.raises(PluginDependencyError, match="Python distribution"):
        PluginCatalog.discover(
            ["Hooks"],
            entry_points=[],
            local=local_settings(),
            config_root=tmp_path,
            core_version=CORE_VERSION,
        )

    assert not marker.exists()


def test_cross_origin_plugin_name_collision_is_rejected_before_import(tmp_path: Path):
    class SharedPlugin(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="installed.shared",
            version="1.0.0",
            requires_core=">=3.1.0.dev2",
        )

    write_plugin(
        tmp_path / "plugins",
        "local.shared",
        plugin_name="SharedPlugin",
        code=(
            "from butterbot.plugin import ButterPlugin\n"
            "\n"
            "class SharedPlugin(ButterPlugin):\n"
            "    pass\n"
        ),
    )
    entry_point = FakeEntryPoint("SharedPlugin", SharedPlugin)

    with pytest.raises(PluginDiscoveryError, match="重复来源"):
        PluginCatalog.discover(
            ["SharedPlugin"],
            entry_points=[entry_point],
            local=local_settings(),
            config_root=tmp_path,
            core_version=CORE_VERSION,
        )

    assert entry_point.loads == 0


def test_hybrid_dependencies_share_one_topological_graph(tmp_path: Path):
    class InstalledProvider(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="installed.provider",
            version="1.0.0",
            requires_core=">=3.1.0.dev2",
        )

    write_plugin(
        tmp_path / "plugins",
        "local.consumer",
        requires_plugins=("installed.provider",),
    )

    catalog = PluginCatalog.discover(
        ["Hooks", "InstalledProvider"],
        entry_points=[FakeEntryPoint("InstalledProvider", InstalledProvider)],
        local=local_settings(),
        config_root=tmp_path,
        core_version=CORE_VERSION,
    )

    assert catalog.plugin_ids == ("installed.provider", "local.consumer")


def test_distribution_can_depend_on_local_plugin(tmp_path: Path):
    class InstalledConsumer(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="installed.consumer",
            version="1.0.0",
            requires_core=">=3.1.0.dev2",
            requires_plugins=("local.provider",),
        )

    write_plugin(tmp_path / "plugins", "local.provider")

    catalog = PluginCatalog.discover(
        ["InstalledConsumer", "Hooks"],
        entry_points=[FakeEntryPoint("InstalledConsumer", InstalledConsumer)],
        local=local_settings(),
        config_root=tmp_path,
        core_version=CORE_VERSION,
    )

    assert catalog.plugin_ids == ("local.provider", "installed.consumer")
