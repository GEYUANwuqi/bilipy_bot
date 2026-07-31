"""插件注册装饰器与基类上下文测试."""

from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import pytest

from butterbot.plugin import ButterPlugin, configure, register
from butterbot.plugin.contracts.hooks import (
    iter_configure_hooks,
    iter_plugin_subscriptions,
)


def test_register_declares_handler_subscriptions_in_definition_order() -> None:
    class BasePlugin(ButterPlugin):
        @register("example.events", "example.first")
        async def first_handler(self, event) -> None:
            del event

    class ExamplePlugin(BasePlugin):
        @register("example.events", "example.second")
        @register("example.events", "example.third")
        async def other_handler(self, event) -> None:
            del event

    subscriptions = iter_plugin_subscriptions(ExamplePlugin())

    assert tuple(handler.__name__ for handler, _ in subscriptions) == (
        "first_handler",
        "other_handler",
        "other_handler",
    )
    assert tuple(declaration.status for _, declaration in subscriptions) == (
        "example.first",
        "example.second",
        "example.third",
    )


def test_subclass_override_can_replace_or_remove_declarations() -> None:
    class BasePlugin(ButterPlugin):
        @register("example.events", "example.base")
        async def handler(self, event) -> None:
            del event

    class DisabledPlugin(BasePlugin):
        async def handler(self, event) -> None:
            del event

    class ReplacedPlugin(BasePlugin):
        @register("other.events", "other.event")
        async def handler(self, event) -> None:
            del event

    assert iter_plugin_subscriptions(DisabledPlugin()) == ()
    subscriptions = iter_plugin_subscriptions(ReplacedPlugin())
    assert len(subscriptions) == 1
    assert subscriptions[0][1].source_kind == "other.events"


def test_base_context_builds_source_ref_and_subscription_spec(tmp_path: Path) -> None:
    class ExamplePlugin(ButterPlugin):
        @register("example.events", "example.ready")
        async def handler(self, event) -> None:
            del event

    plugin = ExamplePlugin()
    plugin._bind_context(
        MappingProxyType({"config_key": "primary", "value": 1}),
        tmp_path,
    )

    assert plugin.settings == {"config_key": "primary", "value": 1}
    assert plugin.resource_root == tmp_path
    assert plugin.config_key == "primary"
    assert plugin.source_ref("example.events").config_key == "primary"
    specs = plugin._subscription_specs()
    assert len(specs) == 1
    assert specs[0].source.source_kind == "example.events"
    assert specs[0].source.config_key == "primary"
    assert specs[0].status == "example.ready"
    assert specs[0].callback.__self__ is plugin


def test_missing_config_key_uses_kind_only_source_ref() -> None:
    plugin = ButterPlugin()

    assert plugin.config_key is None
    assert plugin.source_ref("example.events").config_key is None


@pytest.mark.asyncio
async def test_default_lifecycle_callbacks_are_noops() -> None:
    plugin = ButterPlugin()

    await plugin.on_start()
    await plugin.on_stop()


def test_register_forwards_filter_and_multiple_match_policy() -> None:
    event_filter = object()

    class ExamplePlugin(ButterPlugin):
        @register(
            "example.events",
            "example.ready",
            event_filter=event_filter,
            allow_multiple=True,
        )
        async def handler(self, event) -> None:
            del event

    spec = ExamplePlugin()._subscription_specs()[0]

    assert spec.event_filter is event_filter
    assert spec.allow_multiple


def test_configure_methods_still_support_source_factory_registration() -> None:
    class BasePlugin(ButterPlugin):
        @configure
        def first_config(self, registrar) -> None:
            del registrar

    class ExamplePlugin(BasePlugin):
        @configure
        def second_config(self, registrar) -> None:
            del registrar

    assert tuple(hook.__name__ for hook in iter_configure_hooks(ExamplePlugin())) == (
        "first_config",
        "second_config",
    )


def test_register_requires_async_handler() -> None:
    def invalid_handler(event) -> None:
        del event

    with pytest.raises(TypeError, match="async Handler"):
        register("example.events", "example.ready")(cast(Any, invalid_handler))
