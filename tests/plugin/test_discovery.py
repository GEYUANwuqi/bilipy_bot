"""插件发现测试."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from butterbot.plugin import (
    PluginBase,
    PluginCatalog,
    PluginCompatibilityError,
    PluginDependencyError,
    PluginDescriptor,
    PluginDiscoveryError,
)

CORE_VERSION = "3.1.0.dev2"


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
    requires: tuple[str, ...] = (),
    provides: tuple[str, ...] = (),
    requires_core: str = ">=3.1.0.dev1",
) -> type[PluginBase]:
    class TestPlugin(PluginBase):
        descriptor = PluginDescriptor(
            plugin_id=plugin_id,
            version="1.0.0",
            requires_core=requires_core,
            requires_plugins=requires,
            provides=provides,
        )

    return TestPlugin


def test_only_enabled_entry_points_are_imported():
    enabled = FakeEntryPoint("example.enabled", make_plugin("example.enabled"))
    disabled = FakeEntryPoint(
        "example.disabled",
        RuntimeError("不应导入"),
    )

    catalog = PluginCatalog.discover(
        ["example.enabled"],
        entry_points=[disabled, enabled],
        core_version=CORE_VERSION,
    )

    assert catalog.plugin_ids == ("example.enabled",)
    assert enabled.loads == 1
    assert disabled.loads == 0


def test_dependencies_are_sorted_before_consumers():
    provider = FakeEntryPoint(
        "example.provider",
        make_plugin("example.provider", provides=("example.events",)),
    )
    consumer = FakeEntryPoint(
        "example.consumer",
        make_plugin(
            "example.consumer",
            requires=("example.provider",),
            provides=("example.handler",),
        ),
    )

    catalog = PluginCatalog.discover(
        ["example.consumer", "example.provider"],
        entry_points=[consumer, provider],
        core_version=CORE_VERSION,
    )

    assert catalog.plugin_ids == ("example.provider", "example.consumer")


@pytest.mark.parametrize(
    ("entry_points", "enabled", "error", "message"),
    [
        (
            [],
            ["example.missing"],
            PluginDiscoveryError,
            "没有对应",
        ),
        (
            [
                FakeEntryPoint("example.same", make_plugin("example.same"), "one"),
                FakeEntryPoint("example.same", make_plugin("example.same"), "two"),
            ],
            ["example.same"],
            PluginDiscoveryError,
            "重复 entry point",
        ),
        (
            [
                FakeEntryPoint(
                    "example.consumer",
                    make_plugin(
                        "example.consumer",
                        requires=("example.provider",),
                    ),
                )
            ],
            ["example.consumer"],
            PluginDependencyError,
            "缺少已启用依赖",
        ),
        (
            [
                FakeEntryPoint(
                    "example.old",
                    make_plugin(
                        "example.old",
                        requires_core=">=9",
                    ),
                )
            ],
            ["example.old"],
            PluginCompatibilityError,
            "要求 ButterBot",
        ),
        (
            [
                FakeEntryPoint(
                    "example.one",
                    make_plugin("example.one", provides=("same.events",)),
                ),
                FakeEntryPoint(
                    "example.two",
                    make_plugin("example.two", provides=("same.events",)),
                ),
            ],
            ["example.one", "example.two"],
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
        "example.one",
        make_plugin("example.one", requires=("example.two",)),
    )
    two = FakeEntryPoint(
        "example.two",
        make_plugin("example.two", requires=("example.one",)),
    )

    with pytest.raises(PluginDependencyError, match="依赖循环"):
        PluginCatalog.discover(
            ["example.one", "example.two"],
            entry_points=[one, two],
            core_version=CORE_VERSION,
        )


def test_entry_point_identity_must_match_descriptor():
    entry_point = FakeEntryPoint(
        "example.alias",
        make_plugin("example.real"),
    )

    with pytest.raises(PluginDiscoveryError, match="plugin_id"):
        PluginCatalog.discover(
            ["example.alias"],
            entry_points=[entry_point],
            core_version=CORE_VERSION,
        )
