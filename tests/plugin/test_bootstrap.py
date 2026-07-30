"""插件 bootstrap 集成测试."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import pytest

from butterbot.app import BotApp
from butterbot.core.data import BaseDataMixin
from butterbot.core.exceptions import ConfigError, SourceError, SourceStartError
from butterbot.core.source import BaseSource
from butterbot.core.types import BaseType
from butterbot.plugin import (
    ButterPlugin,
    Event,
    PluginDescriptor,
    PluginRegistrationError,
    PluginState,
    SourceRef,
    SubscriptionSpec,
    bootstrap_app,
    validate_plugin_config,
)

CORE_VERSION = "3.1.0.dev2"


class PluginType(BaseType):
    ALL = "plugin.all"
    READY = "plugin.ready"


class PluginData(BaseDataMixin):
    def __init__(self, value: str) -> None:
        self.value = value


class PluginSource(BaseSource):
    source_kind = "example.events"
    supported_types = PluginType

    def __init__(self, *, fail_start: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.fail_start = fail_start

    async def on_start(self) -> None:
        if self.fail_start:
            raise RuntimeError("start failed")

    async def on_stop(self) -> None:
        pass

    async def emit(self, value: str) -> None:
        await self.ctx.bus.publish(
            self.uuid,
            Event(PluginData(value), PluginType.READY),
        )


@dataclass
class FakeEntryPoint:
    name: str
    target: Any
    value: str = "tests.fake:Plugin"

    def load(self) -> Any:
        return self.target


class ProviderPlugin(ButterPlugin):
    descriptor = PluginDescriptor(
        plugin_id="example.provider",
        version="1.0.0",
        requires_core=">=3.1.0.dev1",
        provides=("example.events",),
    )

    def register_config(self, registrar) -> None:
        registrar.register_builder("example", dict)
        registrar.register_factory(
            "example",
            PluginSource,
            factory_id="source",
        )


class ConsumerPlugin(ButterPlugin):
    descriptor = PluginDescriptor(
        plugin_id="example.consumer",
        version="1.0.0",
        requires_core=">=3.1.0.dev1",
        requires_plugins=("example.provider",),
        provides=("example.handler",),
    )
    received: asyncio.Queue[str] | None = None

    async def register(self, registrar) -> None:
        type(self).received = asyncio.Queue()

        async def handler(event: Event) -> None:
            queue = type(self).received
            assert queue is not None
            await queue.put(event.data.value)

        registrar.add_subscription(
            SubscriptionSpec(
                source=SourceRef("example.events", "primary"),
                status="plugin.ready",
                callback=handler,
            )
        )


def write_config(
    path: Path,
    *,
    source_arguments: str = "{}",
    enabled: tuple[str, ...] = ("example.consumer", "example.provider"),
) -> None:
    enabled_yaml = "\n".join("    - %s" % plugin_id for plugin_id in enabled)
    path.write_text(
        "plugins:\n"
        "  enabled:\n"
        f"{enabled_yaml}\n"
        "sources:\n"
        "  primary:\n"
        "    source_name: example\n"
        "    kwarg:\n"
        f"      source: {source_arguments}\n",
        encoding="utf-8",
    )


def entry_points(*extra: FakeEntryPoint) -> tuple[FakeEntryPoint, ...]:
    return (
        FakeEntryPoint("example.provider", ProviderPlugin),
        FakeEntryPoint("example.consumer", ConsumerPlugin),
        *extra,
    )


@pytest.mark.asyncio
async def test_bootstrap_routes_across_independent_plugins(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path)
    app = bootstrap_app(
        config_path,
        entry_points=entry_points(),
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    source = app.get_source(SourceRef("example.events", "primary"))
    assert isinstance(source, PluginSource)
    catalog_entry = app.manager.source_catalog.by_owner("example.provider")
    assert tuple(item.source_id for item in catalog_entry) == (source.uuid,)

    await app.start()
    await source.emit("ready")
    assert ConsumerPlugin.received is not None
    assert await asyncio.wait_for(ConsumerPlugin.received.get(), timeout=1) == "ready"
    assert [status.state for status in manager.statuses] == [
        PluginState.STARTED,
        PluginState.STARTED,
    ]
    assert [receipt.owner_id for receipt in manager.receipts] == [
        "example.provider",
        "example.consumer",
    ]

    await app.close()

    assert app.manager.sources == {}
    assert app.bus.pending_callbacks == 0
    assert [status.state for status in manager.statuses] == [
        PluginState.CLOSED,
        PluginState.CLOSED,
    ]
    assert manager.receipts == ()


@pytest.mark.asyncio
async def test_plugin_lifecycle_hooks_follow_dependency_order_and_restart(
    tmp_path: Path,
):
    lifecycle: list[str] = []

    class LifecycleProvider(ProviderPlugin):
        async def on_start(self) -> None:
            lifecycle.append("start:provider")

        async def on_stop(self) -> None:
            lifecycle.append("stop:provider")

    class LifecycleConsumer(ConsumerPlugin):
        async def on_start(self) -> None:
            lifecycle.append("start:consumer")

        async def on_stop(self) -> None:
            lifecycle.append("stop:consumer")

    config_path = tmp_path / "config.yaml"
    write_config(config_path)
    app = bootstrap_app(
        config_path,
        entry_points=(
            FakeEntryPoint("example.provider", LifecycleProvider),
            FakeEntryPoint("example.consumer", LifecycleConsumer),
        ),
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    await app.start()
    assert lifecycle == ["start:provider", "start:consumer"]
    assert all(status.state == PluginState.STARTED for status in manager.statuses)

    await app.stop()
    assert lifecycle[-2:] == ["stop:consumer", "stop:provider"]
    assert all(status.state == PluginState.REGISTERED for status in manager.statuses)

    await app.start()
    await app.close()
    assert lifecycle == [
        "start:provider",
        "start:consumer",
        "stop:consumer",
        "stop:provider",
        "start:provider",
        "start:consumer",
        "stop:consumer",
        "stop:provider",
    ]


@pytest.mark.asyncio
async def test_plugin_start_failure_runs_stop_hooks_and_rolls_back(
    tmp_path: Path,
):
    lifecycle: list[str] = []

    class LifecycleProvider(ProviderPlugin):
        async def on_start(self) -> None:
            lifecycle.append("start:provider")

        async def on_stop(self) -> None:
            lifecycle.append("stop:provider")

    class FailingConsumer(ConsumerPlugin):
        async def on_start(self) -> None:
            lifecycle.append("start:consumer")
            raise RuntimeError("plugin start failed")

        async def on_stop(self) -> None:
            lifecycle.append("stop:consumer")

    config_path = tmp_path / "config.yaml"
    write_config(config_path)
    app = bootstrap_app(
        config_path,
        entry_points=(
            FakeEntryPoint("example.provider", LifecycleProvider),
            FakeEntryPoint("example.consumer", FailingConsumer),
        ),
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    with pytest.raises(PluginRegistrationError) as exc_info:
        await app.start()

    assert exc_info.value.plugin_id == "example.consumer"
    assert exc_info.value.phase == "starting"
    assert lifecycle == [
        "start:provider",
        "start:consumer",
        "stop:consumer",
        "stop:provider",
    ]
    assert app.manager.sources == {}
    assert app.bus.pending_callbacks == 0
    assert [status.state for status in manager.statuses] == [
        PluginState.CLOSED,
        PluginState.FAILED,
    ]
    await app.close()


@pytest.mark.asyncio
async def test_plugin_start_cancellation_rolls_back_before_propagating(
    tmp_path: Path,
):
    stopped = False

    class CancelledProvider(ProviderPlugin):
        async def on_start(self) -> None:
            raise asyncio.CancelledError

        async def on_stop(self) -> None:
            nonlocal stopped
            stopped = True

    config_path = tmp_path / "config.yaml"
    write_config(config_path, enabled=("example.provider",))
    app = bootstrap_app(
        config_path,
        entry_points=(FakeEntryPoint("example.provider", CancelledProvider),),
        core_version=CORE_VERSION,
    )

    with pytest.raises(asyncio.CancelledError):
        await app.start()

    assert stopped
    assert app.manager.sources == {}
    assert app.bus.pending_callbacks == 0
    await app.close()


@pytest.mark.asyncio
async def test_plugin_stop_cancellation_does_not_skip_cleanup(tmp_path: Path):
    stopped: list[str] = []

    class CancelledProvider(ProviderPlugin):
        async def on_stop(self) -> None:
            stopped.append("provider")
            raise asyncio.CancelledError

    class ClosingConsumer(ConsumerPlugin):
        async def on_stop(self) -> None:
            stopped.append("consumer")

    config_path = tmp_path / "config.yaml"
    write_config(config_path)
    app = bootstrap_app(
        config_path,
        entry_points=(
            FakeEntryPoint("example.provider", CancelledProvider),
            FakeEntryPoint("example.consumer", ClosingConsumer),
        ),
        core_version=CORE_VERSION,
    )

    await app.start()
    with pytest.raises(asyncio.CancelledError):
        await app.close()

    assert stopped == ["consumer", "provider"]
    assert app.manager.sources == {}
    assert app.bus.pending_callbacks == 0
    assert app.closed


def test_validate_uses_same_config_and_runtime_registration(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path)

    validate_plugin_config(
        config_path,
        entry_points=entry_points(),
        core_version=CORE_VERSION,
    )


def test_environment_can_override_enabled_allow_list(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("plugins:\n  enabled: []\n", encoding="utf-8")

    app = bootstrap_app(
        config_path,
        environ={
            "BUTTERBOT__PLUGINS__ENABLED": ("[example.provider, example.consumer]")
        },
        entry_points=entry_points(),
        core_version=CORE_VERSION,
    )

    assert app._plugin_manager is not None
    assert app._plugin_manager.plugin_ids == (
        "example.provider",
        "example.consumer",
    )
    asyncio.run(app.close())


@pytest.mark.asyncio
async def test_runtime_failure_rolls_back_all_registration(tmp_path: Path):
    class FailingConsumer(ConsumerPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.failing",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
            requires_plugins=("example.provider",),
        )

        async def register(self, registrar) -> None:
            await super().register(registrar)
            raise RuntimeError("register failed")

    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        enabled=("example.provider", "example.failing"),
    )
    points = (
        FakeEntryPoint("example.provider", ProviderPlugin),
        FakeEntryPoint("example.failing", FailingConsumer),
    )
    app = bootstrap_app(
        config_path,
        entry_points=points,
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    with pytest.raises(PluginRegistrationError, match="example.failing"):
        await app.start()

    assert app.manager.sources == {}
    assert app.bus.remove_subscribers_by_owner("example.failing") == 0
    assert "example" not in manager._builder_registry.names
    assert manager._factory_registry.names("example") == ()
    states = {status.plugin_id: status.state for status in manager.statuses}
    assert states["example.provider"] == PluginState.CLOSED
    assert states["example.failing"] == PluginState.FAILED
    await app.close()


@pytest.mark.asyncio
async def test_runtime_failure_marks_transitive_dependents_blocked(
    tmp_path: Path,
):
    class FailingPlugin(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.failing",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
            requires_plugins=("example.provider",),
        )

        async def register(self, registrar) -> None:
            del registrar
            raise RuntimeError("register failed")

    class BlockedPlugin(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.blocked",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
            requires_plugins=("example.failing",),
        )
        called = False

        async def register(self, registrar) -> None:
            del registrar
            type(self).called = True

    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        enabled=(
            "example.blocked",
            "example.failing",
            "example.provider",
        ),
    )
    app = bootstrap_app(
        config_path,
        entry_points=(
            FakeEntryPoint("example.provider", ProviderPlugin),
            FakeEntryPoint("example.failing", FailingPlugin),
            FakeEntryPoint("example.blocked", BlockedPlugin),
        ),
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    with pytest.raises(PluginRegistrationError):
        await app.start()

    statuses = {status.plugin_id: status for status in manager.statuses}
    assert statuses["example.provider"].state == PluginState.CLOSED
    assert statuses["example.failing"].state == PluginState.FAILED
    assert statuses["example.blocked"].state == PluginState.BLOCKED
    assert "example.failing" in (statuses["example.blocked"].error or "")
    assert not BlockedPlugin.called
    await app.close()


def test_config_failure_rolls_back_builder_and_factory_receipts(tmp_path: Path):
    class FailingConfigPlugin(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.config-failure",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
        )
        registrations: ClassVar[tuple[Any, ...]] = ()

        def register_config(self, registrar) -> None:
            builder = registrar.register_builder("failing-config", dict)
            factory = registrar.register_factory(
                "failing-config",
                PluginSource,
                factory_id="source",
            )
            type(self).registrations = (builder, factory)
            raise RuntimeError("config failed")

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n  enabled: [example.config-failure]\n",
        encoding="utf-8",
    )

    with pytest.raises(PluginRegistrationError) as exc_info:
        bootstrap_app(
            config_path,
            entry_points=[
                FakeEntryPoint(
                    "example.config-failure",
                    FailingConfigPlugin,
                )
            ],
            core_version=CORE_VERSION,
        )

    assert exc_info.value.plugin_id == "example.config-failure"
    assert exc_info.value.phase == "configuring"
    assert isinstance(exc_info.value.cause, RuntimeError)
    assert FailingConfigPlugin.registrations
    assert all(
        not registration.unregister()
        for registration in FailingConfigPlugin.registrations
    )


@pytest.mark.asyncio
async def test_registration_cancellation_still_rolls_back(tmp_path: Path):
    class CancelledPlugin(ProviderPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.cancelled",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
            provides=("example.cancelled.events",),
        )

        def register_config(self, registrar) -> None:
            registrar.register_builder("cancelled", dict)

        async def register(self, registrar) -> None:
            registrar.add_source(PluginSource, config_key="cancelled")
            raise asyncio.CancelledError

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n  enabled: [example.cancelled]\n",
        encoding="utf-8",
    )
    app = bootstrap_app(
        config_path,
        entry_points=[
            FakeEntryPoint("example.cancelled", CancelledPlugin),
        ],
        core_version=CORE_VERSION,
    )

    with pytest.raises(asyncio.CancelledError):
        await app.start()

    assert app.manager.sources == {}
    assert app.bus.pending_callbacks == 0
    await app.close()


@pytest.mark.asyncio
async def test_source_start_failure_rolls_back_plugin_receipts(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        source_arguments="{fail_start: true}",
        enabled=("example.provider",),
    )
    app = bootstrap_app(
        config_path,
        entry_points=[FakeEntryPoint("example.provider", ProviderPlugin)],
        core_version=CORE_VERSION,
    )

    with pytest.raises(SourceStartError):
        await app.start()

    assert app.manager.sources == {}
    assert app.bus.pending_callbacks == 0
    await app.close()


@pytest.mark.asyncio
async def test_plugins_close_in_reverse_dependency_order_and_only_once(
    tmp_path: Path,
):
    closed: list[str] = []

    class ClosingProvider(ProviderPlugin):
        async def register(self, registrar) -> None:
            registrar.on_close(lambda: closed.append("provider"))

    class ClosingConsumer(ConsumerPlugin):
        async def register(self, registrar) -> None:
            await super().register(registrar)
            registrar.on_close(lambda: closed.append("consumer"))

    config_path = tmp_path / "config.yaml"
    write_config(config_path)
    app = bootstrap_app(
        config_path,
        entry_points=(
            FakeEntryPoint("example.provider", ClosingProvider),
            FakeEntryPoint("example.consumer", ClosingConsumer),
        ),
        core_version=CORE_VERSION,
    )

    await app.start()
    manager = app._plugin_manager
    assert manager is not None
    assert [len(receipt.cleanups) for receipt in manager.receipts] == [1, 1]
    await app.close()
    await app.close()

    assert closed == ["consumer", "provider"]
    assert app.bus.pending_callbacks == 0


def test_plugin_owned_logical_source_conflict_fails_during_build(tmp_path: Path):
    class DuplicateSource(PluginSource):
        pass

    class DuplicateProvider(ProviderPlugin):
        def register_config(self, registrar) -> None:
            registrar.register_builder("example", dict)
            registrar.register_factory(
                "example",
                PluginSource,
                factory_id="one",
            )
            registrar.register_factory(
                "example",
                DuplicateSource,
                factory_id="two",
            )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n"
        "  enabled: [example.provider]\n"
        "sources:\n"
        "  primary:\n"
        "    source_name: example\n"
        "    kwarg:\n"
        "      one: {}\n"
        "      two: {}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        PluginRegistrationError,
        match="<application>",
    ) as exc_info:
        bootstrap_app(
            config_path,
            entry_points=[FakeEntryPoint("example.provider", DuplicateProvider)],
            core_version=CORE_VERSION,
        )

    config_error = exc_info.value.__cause__
    assert isinstance(config_error, ConfigError)
    assert "自动实例化 'two' 失败" in str(config_error)
    assert isinstance(config_error.__cause__, SourceError)


def test_app_factory_must_accept_bootstrap_dependencies(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("plugins:\n  enabled: []\n", encoding="utf-8")

    def invalid_factory() -> BotApp:
        return BotApp()

    with pytest.raises(ConfigError, match="必须接受关键字参数"):
        bootstrap_app(config_path, app_factory=invalid_factory)
