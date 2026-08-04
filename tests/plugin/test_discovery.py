"""插件发现测试."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from butterbot.plugin import (
    ButterPlugin,
    PluginCompatibilityError,
    PluginDependencyError,
    PluginDescriptor,
    PluginDiscoveryError,
)
from butterbot.plugin.discovery.catalog import PluginCatalog

CORE_VERSION = "3.1.0"


@dataclass
class FakeEntryPoint:
    name: str
    target: Any
    value: str = "tests.fake:Plugin"
    loads: int = 0

    def load(self) -> Any:
        self.loads += 1
        if isinstance(self.target, BaseException):
            raise self.target
        return self.target


def make_plugin(
    plugin_id: str,
    *,
    class_name: str,
    requires: tuple[str, ...] = (),
    provides: tuple[str, ...] = (),
    requires_core: str = ">=3.1,<4",
) -> type[ButterPlugin]:
    descriptor = PluginDescriptor(
        plugin_id=plugin_id,
        version="1.0.0",
        requires_core=requires_core,
        requires_plugins=requires,
        provides=provides,
    )
    return type(class_name, (ButterPlugin,), {"descriptor": descriptor})


def test_only_enabled_entry_points_are_imported():
    enabled = FakeEntryPoint(
        "ExampleEnabledPlugin",
        make_plugin("example.enabled", class_name="ExampleEnabledPlugin"),
    )
    disabled = FakeEntryPoint(
        "ExampleDisabledPlugin",
        RuntimeError("不应导入"),
    )

    catalog = PluginCatalog.discover(
        ["ExampleEnabledPlugin"],
        entry_points=[disabled, enabled],
        core_version=CORE_VERSION,
    )

    assert catalog.plugin_ids == ("example.enabled",)
    assert not hasattr(catalog.plugins[0], "plugin")
    assert enabled.loads == 1
    assert disabled.loads == 0


def test_distribution_is_selected_by_plugin_name_and_keeps_stable_id():
    entry_point = FakeEntryPoint(
        "ExampleFeedPlugin",
        make_plugin("example.feed", class_name="ExampleFeedPlugin"),
    )

    catalog = PluginCatalog.discover(
        ["ExampleFeedPlugin"],
        entry_points=[entry_point],
        core_version=CORE_VERSION,
    )

    assert catalog.selected_names == ("ExampleFeedPlugin",)
    assert catalog.plugin_ids == ("example.feed",)
    assert catalog.candidates[0].plugin_id is None
    assert catalog.candidates[0].plugin_name == "ExampleFeedPlugin"


@pytest.mark.parametrize(
    "plugin_name", ("Display Plugin", "bad-name", "bad\nname", "class", "x" * 101)
)
def test_entry_point_rejects_invalid_class_name(plugin_name: str):
    with pytest.raises(PluginDiscoveryError, match="plugin_name"):
        PluginCatalog.index_candidates(
            entry_points=[FakeEntryPoint(plugin_name, object())],
        )


def test_distribution_plugin_must_inherit_butter_plugin():
    class DuckPlugin:
        descriptor = PluginDescriptor(
            plugin_id="example.duck",
            version="1.0.0",
            requires_core=">=3.1,<4",
        )

    with pytest.raises(PluginDiscoveryError, match="ButterPlugin"):
        PluginCatalog.discover(
            ["DuckPlugin"],
            entry_points=[FakeEntryPoint("DuckPlugin", DuckPlugin)],
            core_version=CORE_VERSION,
        )


@pytest.mark.parametrize(
    ("core_version", "expected"),
    (
        ("3.1.0", True),
        ("3.99.0", True),
        ("4.0.0", False),
    ),
)
def test_stable_plugin_requirement_covers_only_current_major(
    core_version: str,
    expected: bool,
):
    """正式版插件模板遵守当前 major 的兼容边界。"""
    descriptor = PluginDescriptor(
        plugin_id="example.stable",
        version="1.0.0",
        requires_core=">=3.1,<4",
    )

    assert descriptor.supports_core(core_version) is expected


def test_dependencies_are_sorted_before_consumers():
    provider = FakeEntryPoint(
        "ExampleProviderPlugin",
        make_plugin(
            "example.provider",
            class_name="ExampleProviderPlugin",
            provides=("example.events",),
        ),
    )
    consumer = FakeEntryPoint(
        "ExampleConsumerPlugin",
        make_plugin(
            "example.consumer",
            class_name="ExampleConsumerPlugin",
            requires=("example.provider",),
            provides=("example.handler",),
        ),
    )

    catalog = PluginCatalog.discover(
        ["ExampleConsumerPlugin", "ExampleProviderPlugin"],
        entry_points=[consumer, provider],
        core_version=CORE_VERSION,
    )

    assert catalog.plugin_ids == ("example.provider", "example.consumer")


@pytest.mark.parametrize(
    ("entry_points", "enabled", "error", "message"),
    [
        (
            [],
            ["MissingPlugin"],
            PluginDiscoveryError,
            "没有对应",
        ),
        (
            [
                FakeEntryPoint(
                    "ExampleSamePlugin",
                    make_plugin("example.same", class_name="ExampleSamePlugin"),
                    "one",
                ),
                FakeEntryPoint(
                    "ExampleSamePlugin",
                    make_plugin("example.same", class_name="ExampleSamePlugin"),
                    "two",
                ),
            ],
            ["ExampleSamePlugin"],
            PluginDiscoveryError,
            "重复 entry point",
        ),
        (
            [
                FakeEntryPoint(
                    "ExampleConsumerPlugin",
                    make_plugin(
                        "example.consumer",
                        class_name="ExampleConsumerPlugin",
                        requires=("example.provider",),
                    ),
                )
            ],
            ["ExampleConsumerPlugin"],
            PluginDependencyError,
            "缺少已启用依赖",
        ),
        (
            [
                FakeEntryPoint(
                    "ExampleOldPlugin",
                    make_plugin(
                        "example.old",
                        class_name="ExampleOldPlugin",
                        requires_core=">=9",
                    ),
                )
            ],
            ["ExampleOldPlugin"],
            PluginCompatibilityError,
            "要求 ButterBot",
        ),
        (
            [
                FakeEntryPoint(
                    "ExampleOnePlugin",
                    make_plugin(
                        "example.one",
                        class_name="ExampleOnePlugin",
                        provides=("same.events",),
                    ),
                ),
                FakeEntryPoint(
                    "ExampleTwoPlugin",
                    make_plugin(
                        "example.two",
                        class_name="ExampleTwoPlugin",
                        provides=("same.events",),
                    ),
                ),
            ],
            ["ExampleOnePlugin", "ExampleTwoPlugin"],
            PluginCompatibilityError,
            "同时由",
        ),
    ],
)
def test_rejects_invalid_catalogs(entry_points, enabled, error, message):
    with pytest.raises(error, match=message):
        PluginCatalog.discover(
            enabled,
            entry_points=entry_points,
            core_version=CORE_VERSION,
        )


def test_rejects_dependency_cycle():
    one = FakeEntryPoint(
        "ExampleOnePlugin",
        make_plugin(
            "example.one",
            class_name="ExampleOnePlugin",
            requires=("example.two",),
        ),
    )
    two = FakeEntryPoint(
        "ExampleTwoPlugin",
        make_plugin(
            "example.two",
            class_name="ExampleTwoPlugin",
            requires=("example.one",),
        ),
    )

    with pytest.raises(PluginDependencyError, match="依赖循环"):
        PluginCatalog.discover(
            ["ExampleOnePlugin", "ExampleTwoPlugin"],
            entry_points=[one, two],
            core_version=CORE_VERSION,
        )


def test_entry_point_name_must_match_implementation_class():
    entry_point = FakeEntryPoint(
        "AliasPlugin",
        make_plugin("example.real", class_name="RealPlugin"),
    )

    with pytest.raises(PluginDiscoveryError, match="实现类名"):
        PluginCatalog.discover(
            ["AliasPlugin"],
            entry_points=[entry_point],
            core_version=CORE_VERSION,
        )


def test_distinct_names_cannot_resolve_to_the_same_plugin_id():
    first = FakeEntryPoint(
        "FirstPlugin",
        make_plugin("example.same", class_name="FirstPlugin"),
    )
    second = FakeEntryPoint(
        "SecondPlugin",
        make_plugin("example.same", class_name="SecondPlugin"),
    )

    with pytest.raises(PluginDiscoveryError, match="重复 plugin_id"):
        PluginCatalog.discover(
            ["FirstPlugin", "SecondPlugin"],
            entry_points=[first, second],
            core_version=CORE_VERSION,
        )
