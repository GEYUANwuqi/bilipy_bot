"""插件 bootstrap 集成测试."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import pytest

from butterbot.app import BotApp, RuntimeConfig
from butterbot.core.api import BaseApi
from butterbot.core.data import BaseDataMixin
from butterbot.core.event import Event
from butterbot.core.exceptions import (
    ConfigError,
    LifecycleError,
    SourceError,
    SourceStartError,
)
from butterbot.core.source import BaseSource
from butterbot.core.types import BaseType
from butterbot.plugin import (
    ButterPlugin,
    PluginBootstrap,
    PluginConfig,
    PluginDescriptor,
    PluginFailurePhase,
    PluginRegistrationError,
    PluginState,
    SourceRef,
    bootstrap_app,
    configure,
    register,
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


class PluginApi(BaseApi):
    def __init__(self, config_key: str) -> None:
        self.config_key = config_key

    @classmethod
    def create(cls, ctx, config_key: str) -> "PluginApi":
        del ctx
        return cls(config_key)


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

    @configure
    def configure_source(self, registrar) -> None:
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

    def __init__(self) -> None:
        type(self).received = asyncio.Queue()

    @register("example.events", "plugin.ready")
    async def handler(self, event: Event) -> None:
        queue = type(self).received
        assert queue is not None
        await queue.put(event.data.value)


def write_config(
    path: Path,
    *,
    source_arguments: str = "{}",
    enabled: tuple[str, ...] = ("ConsumerPlugin", "ProviderPlugin"),
) -> None:
    enabled_yaml = "\n".join("    - %s" % plugin_id for plugin_id in enabled)
    path.write_text(
        "plugins:\n"
        "  enabled: true\n"
        "  plugin_list:\n"
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
        FakeEntryPoint("ProviderPlugin", ProviderPlugin),
        FakeEntryPoint("ConsumerPlugin", ConsumerPlugin),
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
async def test_plugin_state_follows_application_restart(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path)
    app = bootstrap_app(
        config_path,
        entry_points=entry_points(),
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    await app.start()
    assert all(status.state == PluginState.STARTED for status in manager.statuses)

    await app.stop()
    assert all(status.state == PluginState.REGISTERED for status in manager.statuses)

    await app.start()
    await app.close()
    assert all(status.state == PluginState.CLOSED for status in manager.statuses)


@pytest.mark.asyncio
async def test_plugin_context_resolves_source_and_api_without_app_import(
    tmp_path: Path,
):
    observed: list[object] = []

    class ContextProvider(ProviderPlugin):
        async def on_start(self) -> None:
            observed.append(self.context.get_source("example.events"))
            observed.append(self.context.get_api(PluginApi))

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n"
        "  enabled: true\n"
        "  plugin_list: [ContextProvider]\n"
        "  config:\n"
        "    example.provider:\n"
        "      config_key: primary\n"
        "sources:\n"
        "  primary:\n"
        "    source_name: example\n"
        "    kwarg:\n"
        "      source: {}\n",
        encoding="utf-8",
    )
    app = bootstrap_app(
        config_path,
        entry_points=[FakeEntryPoint("ContextProvider", ContextProvider)],
        core_version=CORE_VERSION,
    )
    source = app.get_source(SourceRef("example.events", "primary"))

    await app.start()

    assert observed[0] is source
    assert isinstance(observed[1], PluginApi)
    assert observed[1].config_key == "primary"
    await app.close()


@pytest.mark.asyncio
async def test_lifecycle_callbacks_follow_dependency_order_and_restart(
    tmp_path: Path,
):
    calls: list[str] = []

    class LifecycleProvider(ProviderPlugin):
        async def on_start(self) -> None:
            calls.append("start:provider")

        async def on_stop(self) -> None:
            calls.append("stop:provider")

    class LifecycleConsumer(ConsumerPlugin):
        async def on_start(self) -> None:
            calls.append("start:consumer")

        async def on_stop(self) -> None:
            calls.append("stop:consumer")

    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        enabled=("LifecycleConsumer", "LifecycleProvider"),
    )
    app = bootstrap_app(
        config_path,
        entry_points=(
            FakeEntryPoint("LifecycleProvider", LifecycleProvider),
            FakeEntryPoint("LifecycleConsumer", LifecycleConsumer),
        ),
        core_version=CORE_VERSION,
    )

    await app.start()
    assert calls == ["start:provider", "start:consumer"]

    await app.stop()
    assert calls == [
        "start:provider",
        "start:consumer",
        "stop:consumer",
        "stop:provider",
    ]

    await app.start()
    await app.close()
    assert calls == [
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
async def test_start_callback_failure_stops_entered_plugins_and_rolls_back(
    tmp_path: Path,
):
    calls: list[str] = []

    class LifecycleProvider(ProviderPlugin):
        async def on_start(self) -> None:
            calls.append("start:provider")

        async def on_stop(self) -> None:
            calls.append("stop:provider")

    class FailingConsumer(ConsumerPlugin):
        async def on_start(self) -> None:
            calls.append("start:consumer")
            raise RuntimeError("plugin start failed")

        async def on_stop(self) -> None:
            calls.append("stop:consumer")

    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        enabled=("FailingConsumer", "LifecycleProvider"),
    )
    app = bootstrap_app(
        config_path,
        entry_points=(
            FakeEntryPoint("LifecycleProvider", LifecycleProvider),
            FakeEntryPoint("FailingConsumer", FailingConsumer),
        ),
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    with pytest.raises(PluginRegistrationError) as exc_info:
        await app.start()

    assert exc_info.value.plugin_id == "example.consumer"
    assert exc_info.value.phase == "starting"
    assert isinstance(exc_info.value.cause, RuntimeError)
    assert calls == [
        "start:provider",
        "start:consumer",
        "stop:consumer",
        "stop:provider",
    ]
    assert app.manager.sources == {}
    states = {status.plugin_id: status.state for status in manager.statuses}
    assert states == {
        "example.provider": PluginState.CLOSED,
        "example.consumer": PluginState.FAILED,
    }
    await app.close()


@pytest.mark.asyncio
async def test_start_callback_cancellation_still_rolls_back(tmp_path: Path):
    calls: list[str] = []

    class LifecycleProvider(ProviderPlugin):
        async def on_start(self) -> None:
            calls.append("start:provider")

        async def on_stop(self) -> None:
            calls.append("stop:provider")

    class CancelledConsumer(ConsumerPlugin):
        async def on_start(self) -> None:
            calls.append("start:consumer")
            raise asyncio.CancelledError()

        async def on_stop(self) -> None:
            calls.append("stop:consumer")

    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        enabled=("CancelledConsumer", "LifecycleProvider"),
    )
    app = bootstrap_app(
        config_path,
        entry_points=(
            FakeEntryPoint("LifecycleProvider", LifecycleProvider),
            FakeEntryPoint("CancelledConsumer", CancelledConsumer),
        ),
        core_version=CORE_VERSION,
    )

    with pytest.raises(asyncio.CancelledError):
        await app.start()

    assert calls == [
        "start:provider",
        "start:consumer",
        "stop:consumer",
        "stop:provider",
    ]
    assert app.manager.sources == {}
    await app.close()


@pytest.mark.asyncio
async def test_stop_callback_cancellation_does_not_skip_remaining_cleanup(
    tmp_path: Path,
):
    calls: list[str] = []

    class LifecycleProvider(ProviderPlugin):
        async def on_stop(self) -> None:
            calls.append("stop:provider")

    class CancelledConsumer(ConsumerPlugin):
        async def on_stop(self) -> None:
            calls.append("stop:consumer")
            raise asyncio.CancelledError()

    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        enabled=("CancelledConsumer", "LifecycleProvider"),
    )
    app = bootstrap_app(
        config_path,
        entry_points=(
            FakeEntryPoint("LifecycleProvider", LifecycleProvider),
            FakeEntryPoint("CancelledConsumer", CancelledConsumer),
        ),
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    await app.start()
    with pytest.raises(asyncio.CancelledError):
        await app.stop()

    assert calls == ["stop:consumer", "stop:provider"]
    assert not app.running
    states = {status.plugin_id: status.state for status in manager.statuses}
    assert states == {
        "example.provider": PluginState.REGISTERED,
        "example.consumer": PluginState.FAILED,
    }
    await app.close()


@pytest.mark.asyncio
async def test_plugin_scope_cleans_tasks_and_callbacks_on_each_stop(
    tmp_path: Path,
):
    calls: list[str] = []
    task_started = asyncio.Event()
    task_cancelled = asyncio.Event()

    class ScopedPlugin(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.scoped",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
        )

        async def on_start(self) -> None:
            async def worker() -> None:
                task_started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    task_cancelled.set()

            self.context.add_cleanup(lambda: calls.append("cleanup:first"))
            self.context.add_cleanup(lambda: calls.append("cleanup:second"))
            self.context.spawn(worker(), name="example.scoped.worker")
            await task_started.wait()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n  enabled: true\n  plugin_list: [ScopedPlugin]\n",
        encoding="utf-8",
    )
    app = bootstrap_app(
        config_path,
        entry_points=[FakeEntryPoint("ScopedPlugin", ScopedPlugin)],
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    await app.start()
    plugin = manager._records["example.scoped"].loaded.instance
    assert plugin.context.scope.task_count == 1

    await app.stop()

    assert task_cancelled.is_set()
    assert calls == ["cleanup:second", "cleanup:first"]
    assert plugin.context.scope.task_count == 0
    assert plugin.context.scope.cleanup_count == 0
    await app.close()


@pytest.mark.asyncio
async def test_partial_start_failure_closes_plugin_scope(tmp_path: Path):
    calls: list[str] = []
    task_started = asyncio.Event()
    task_cancelled = asyncio.Event()

    class FailingScopedPlugin(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.scoped-failure",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
        )

        async def on_start(self) -> None:
            async def worker() -> None:
                task_started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    task_cancelled.set()

            self.context.spawn(worker())
            self.context.add_cleanup(lambda: calls.append("cleanup"))
            await task_started.wait()
            raise RuntimeError("failed after allocating resources")

        async def on_stop(self) -> None:
            calls.append("stop")

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n  enabled: true\n  plugin_list: [FailingScopedPlugin]\n",
        encoding="utf-8",
    )
    app = bootstrap_app(
        config_path,
        entry_points=[FakeEntryPoint("FailingScopedPlugin", FailingScopedPlugin)],
        core_version=CORE_VERSION,
    )

    with pytest.raises(PluginRegistrationError):
        await app.start()

    assert task_cancelled.is_set()
    assert calls == ["stop", "cleanup"]
    await app.close()


@pytest.mark.asyncio
async def test_start_timeout_is_rolled_back_and_recorded(tmp_path: Path):
    calls: list[str] = []

    class HangingPlugin(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.hanging-start",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
        )

        async def on_start(self) -> None:
            await asyncio.Event().wait()

        async def on_stop(self) -> None:
            calls.append("stop")

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n"
        "  enabled: true\n"
        "  plugin_list: [HangingPlugin]\n"
        "  lifecycle:\n"
        "    start_timeout: 0.01\n",
        encoding="utf-8",
    )
    app = bootstrap_app(
        config_path,
        entry_points=[FakeEntryPoint("HangingPlugin", HangingPlugin)],
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    with pytest.raises(PluginRegistrationError) as exc_info:
        await app.start()

    assert isinstance(exc_info.value.cause, TimeoutError)
    assert calls == ["stop"]
    failure = manager.statuses[0].failures[-1]
    assert failure.phase == PluginFailurePhase.STARTING
    assert failure.timed_out
    assert not manager.statuses[0].healthy
    await app.close()


@pytest.mark.asyncio
async def test_stop_timeout_does_not_skip_dependencies_and_is_recorded(
    tmp_path: Path,
):
    calls: list[str] = []

    class TimeoutProvider(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.timeout-provider",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
        )

        async def on_stop(self) -> None:
            calls.append("stop:provider")

    class TimeoutConsumer(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.timeout-consumer",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
            requires_plugins=("example.timeout-provider",),
        )

        async def on_stop(self) -> None:
            calls.append("stop:consumer")
            await asyncio.Event().wait()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n"
        "  enabled: true\n"
        "  plugin_list:\n"
        "    - TimeoutConsumer\n"
        "    - TimeoutProvider\n"
        "  lifecycle:\n"
        "    stop_timeout: 0.01\n",
        encoding="utf-8",
    )
    app = bootstrap_app(
        config_path,
        entry_points=(
            FakeEntryPoint("TimeoutProvider", TimeoutProvider),
            FakeEntryPoint("TimeoutConsumer", TimeoutConsumer),
        ),
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    await app.start()
    await app.stop()

    assert calls == ["stop:consumer", "stop:provider"]
    statuses = {status.plugin_id: status for status in manager.statuses}
    failure = statuses["example.timeout-consumer"].failures[-1]
    assert failure.phase == PluginFailurePhase.STOPPING
    assert failure.timed_out
    assert statuses["example.timeout-consumer"].state == PluginState.FAILED
    with pytest.raises(LifecycleError, match="不能重新启动"):
        await app.start()

    await app.close()
    statuses = {status.plugin_id: status for status in manager.statuses}
    assert statuses["example.timeout-consumer"].state == PluginState.FAILED
    assert statuses["example.timeout-provider"].state == PluginState.CLOSED


@pytest.mark.asyncio
async def test_background_task_failure_is_recorded_without_stopping_plugin(
    tmp_path: Path,
):
    finished = asyncio.Event()

    class BackgroundFailurePlugin(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.background-failure",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
        )
        task: ClassVar[asyncio.Task[None] | None] = None

        async def on_start(self) -> None:
            async def fail() -> None:
                finished.set()
                raise RuntimeError("background failed")

            type(self).task = self.context.spawn(fail())

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n  enabled: true\n  plugin_list: [BackgroundFailurePlugin]\n",
        encoding="utf-8",
    )
    app = bootstrap_app(
        config_path,
        entry_points=[
            FakeEntryPoint("BackgroundFailurePlugin", BackgroundFailurePlugin)
        ],
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    await app.start()
    await finished.wait()
    task = BackgroundFailurePlugin.task
    assert task is not None
    await asyncio.wait({task})
    await asyncio.sleep(0)

    status = manager.statuses[0]
    assert status.state == PluginState.STARTED
    assert not status.healthy
    assert status.failures[-1].phase == PluginFailurePhase.BACKGROUND
    assert status.failures[-1].error_type == "RuntimeError"
    await app.close()


@pytest.mark.asyncio
async def test_scope_cleanup_timeout_is_bounded_and_recorded(tmp_path: Path):
    cleanup_started = asyncio.Event()

    class HangingCleanupPlugin(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.hanging-cleanup",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
        )

        async def on_start(self) -> None:
            async def cleanup() -> None:
                cleanup_started.set()
                await asyncio.Event().wait()

            self.context.add_cleanup(cleanup)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n"
        "  enabled: true\n"
        "  plugin_list: [HangingCleanupPlugin]\n"
        "  lifecycle:\n"
        "    cleanup_timeout: 0.01\n",
        encoding="utf-8",
    )
    app = bootstrap_app(
        config_path,
        entry_points=[FakeEntryPoint("HangingCleanupPlugin", HangingCleanupPlugin)],
        core_version=CORE_VERSION,
    )
    manager = app._plugin_manager
    assert manager is not None

    await app.start()
    await app.close()

    assert cleanup_started.is_set()
    status = manager.statuses[0]
    assert status.state == PluginState.FAILED
    assert any(
        failure.phase == PluginFailurePhase.CLEANING and failure.timed_out
        for failure in status.failures
    )


def test_typed_plugin_config_fails_before_application_build(tmp_path: Path):
    class TypedConfig(PluginConfig):
        account: str
        retries: int = 3

    class TypedPlugin(ButterPlugin[TypedConfig]):
        descriptor = PluginDescriptor(
            plugin_id="example.typed-config",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
        )
        config_model = TypedConfig

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n"
        "  enabled: true\n"
        "  plugin_list: [TypedPlugin]\n"
        "  config:\n"
        "    example.typed-config:\n"
        "      account: primary\n"
        "      unexpected: rejected\n",
        encoding="utf-8",
    )
    bootstrap = PluginBootstrap(
        config_path,
        entry_points=[FakeEntryPoint("TypedPlugin", TypedPlugin)],
        core_version=CORE_VERSION,
    )

    with pytest.raises(PluginRegistrationError) as exc_info:
        bootstrap.build()

    assert exc_info.value.phase == "configuring"
    assert type(exc_info.value.cause).__name__ == "ValidationError"
    manager = bootstrap.manager
    assert manager is not None
    failure = manager.statuses[0].failures[-1]
    assert failure.phase == PluginFailurePhase.CONFIGURING
    assert failure.error_type == "ValidationError"


def test_validate_uses_same_config_and_runtime_registration(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path)

    validate_plugin_config(
        config_path,
        entry_points=entry_points(),
        core_version=CORE_VERSION,
    )


def test_environment_can_override_plugin_list(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n  enabled: true\n  plugin_list: []\n",
        encoding="utf-8",
    )

    app = bootstrap_app(
        config_path,
        environ={
            "BUTTERBOT__PLUGINS__PLUGIN_LIST": ("[ProviderPlugin, ConsumerPlugin]")
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


def test_disabled_plugin_system_does_not_import_configured_candidates(
    tmp_path: Path,
):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "plugins:\n  enabled: false\n  plugin_list: [DisabledPlugin]\n",
        encoding="utf-8",
    )

    app = bootstrap_app(
        config_path,
        entry_points=[FakeEntryPoint("DisabledPlugin", RuntimeError("不应导入"))],
        core_version=CORE_VERSION,
    )

    assert app._plugin_manager is not None
    assert app._plugin_manager.plugin_ids == ()
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

        def source_ref(self, source_kind: str):
            del source_kind
            raise RuntimeError("register failed")

    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        enabled=("ProviderPlugin", "FailingConsumer"),
    )
    points = (
        FakeEntryPoint("ProviderPlugin", ProviderPlugin),
        FakeEntryPoint("FailingConsumer", FailingConsumer),
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

        @register("missing.events", "missing.event")
        async def handler(self, event: Event) -> None:
            del event

    class BlockedPlugin(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.blocked",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
            requires_plugins=("example.failing",),
        )

        @register("example.events", "plugin.ready")
        async def handler(self, event: Event) -> None:
            del event

    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        enabled=(
            "BlockedPlugin",
            "FailingPlugin",
            "ProviderPlugin",
        ),
    )
    app = bootstrap_app(
        config_path,
        entry_points=(
            FakeEntryPoint("ProviderPlugin", ProviderPlugin),
            FakeEntryPoint("FailingPlugin", FailingPlugin),
            FakeEntryPoint("BlockedPlugin", BlockedPlugin),
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
    await app.close()


def test_config_failure_rolls_back_builder_and_factory_receipts(tmp_path: Path):
    class FailingConfigPlugin(ButterPlugin):
        descriptor = PluginDescriptor(
            plugin_id="example.config-failure",
            version="1.0.0",
            requires_core=">=3.1.0.dev1",
        )
        registrations: ClassVar[tuple[Any, ...]] = ()

        @configure
        def fail_configuration(self, registrar) -> None:
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
        "plugins:\n  enabled: true\n  plugin_list: [FailingConfigPlugin]\n",
        encoding="utf-8",
    )

    with pytest.raises(PluginRegistrationError) as exc_info:
        bootstrap_app(
            config_path,
            entry_points=[
                FakeEntryPoint(
                    "FailingConfigPlugin",
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
async def test_source_start_failure_rolls_back_plugin_receipts(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        source_arguments="{fail_start: true}",
        enabled=("ProviderPlugin",),
    )
    app = bootstrap_app(
        config_path,
        entry_points=[FakeEntryPoint("ProviderPlugin", ProviderPlugin)],
        core_version=CORE_VERSION,
    )

    with pytest.raises(SourceStartError):
        await app.start()

    assert app.manager.sources == {}
    assert app.bus.pending_callbacks == 0
    await app.close()


def test_plugin_owned_logical_source_conflict_fails_during_build(tmp_path: Path):
    class DuplicateSource(PluginSource):
        pass

    class DuplicateProvider(ProviderPlugin):
        @configure
        def configure_source(self, registrar) -> None:
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
        "  enabled: true\n"
        "  plugin_list: [DuplicateProvider]\n"
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
            entry_points=[FakeEntryPoint("DuplicateProvider", DuplicateProvider)],
            core_version=CORE_VERSION,
        )

    config_error = exc_info.value.__cause__
    assert isinstance(config_error, ConfigError)
    assert "自动实例化 'two' 失败" in str(config_error)
    assert isinstance(config_error.__cause__, SourceError)


def test_application_entry_must_accept_bootstrap_dependencies(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("plugins:\n  enabled: false\n", encoding="utf-8")

    def invalid_application() -> BotApp:
        return BotApp()

    with pytest.raises(ConfigError, match="必须接受关键字参数"):
        bootstrap_app(config_path, application=invalid_application)


def test_application_instance_is_adopted_and_bound(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("plugins:\n  enabled: false\n", encoding="utf-8")
    app = BotApp(RuntimeConfig())
    bootstrap = PluginBootstrap(config_path)

    built = bootstrap.build(app)

    assert built is app
    assert bootstrap.manager is not None
    assert app._plugin_manager is bootstrap.manager
