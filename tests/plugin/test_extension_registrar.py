import asyncio

import pytest

from butterbot.app import BotApp, RuntimeConfig
from butterbot.core.data import BaseDataMixin
from butterbot.core.exceptions import LifecycleError, SourceError
from butterbot.core.source import BaseSource
from butterbot.core.types import BaseType
from butterbot.plugin import Event, ExtensionRegistrar, SourceRef, SubscriptionSpec


class PrototypeType(BaseType):
    ALL = "prototype.all"
    READY = "prototype.ready"


class PrototypeData(BaseDataMixin):
    def __init__(self, value: str) -> None:
        self.value = value


class PrototypeSource(BaseSource):
    source_kind = "prototype.events"
    supported_types = PrototypeType

    async def on_start(self) -> None:
        pass

    async def on_stop(self) -> None:
        pass

    async def emit(self, value: str) -> None:
        await self.ctx.bus.publish(
            self.uuid,
            Event(data=PrototypeData(value=value), status=PrototypeType.READY),
        )


@pytest.mark.asyncio
async def test_source_and_handler_extensions_are_decoupled_by_source_ref():
    """Handler 原型无需知道 Source class 或运行时 UUID."""
    app = BotApp(RuntimeConfig())
    provider = ExtensionRegistrar(app, "example.provider")
    source = provider.add_source(PrototypeSource, config_key="primary")
    provider.commit()

    received: asyncio.Queue[str] = asyncio.Queue()

    async def handler(event: Event) -> None:
        await received.put(event.data.value)

    consumer = ExtensionRegistrar(app, "example.consumer")
    handles = consumer.add_subscription(
        SubscriptionSpec(
            source=SourceRef("prototype.events", "primary"),
            status=PrototypeType.READY,
            callback=handler,
        )
    )
    consumer.commit()

    await app.start()
    await source.emit("first")
    assert await asyncio.wait_for(received.get(), timeout=1) == "first"
    assert len(handles) == 1
    assert handles[0].owner_id == "example.consumer"

    await consumer.aclose()
    await source.emit("ignored")
    await asyncio.sleep(0)
    assert received.empty()
    assert app.get_source(source.uuid) is source

    await provider.aclose()
    assert app.get_source(source.uuid) is None
    await app.close()


@pytest.mark.asyncio
async def test_registration_context_rolls_back_on_failure():
    app = BotApp(RuntimeConfig())
    registrar = ExtensionRegistrar(app, "example.failure")

    with pytest.raises(RuntimeError, match="registration failed"):
        async with registrar:
            source = registrar.add_source(
                PrototypeSource,
                config_key="temporary",
            )

            async def handler(event: Event) -> None:
                pass

            registrar.add_subscription(
                SubscriptionSpec(
                    SourceRef("prototype.events", "temporary"),
                    PrototypeType.READY,
                    handler,
                )
            )
            raise RuntimeError("registration failed")

    assert registrar.closed
    assert app.get_source(source.uuid) is None
    assert app.bus.remove_subscribers_by_owner("example.failure") == 0
    await app.close()


@pytest.mark.asyncio
async def test_close_cancels_only_owned_handler_after_timeout():
    app = BotApp(RuntimeConfig())
    source = app.add_source(PrototypeSource, config_key="primary")
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def handler(event: Event) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    registrar = ExtensionRegistrar(
        app,
        "example.consumer",
        drain_timeout=0,
    )
    registrar.add_subscription(
        SubscriptionSpec(
            SourceRef("prototype.events", "primary"),
            PrototypeType.READY,
            handler,
        )
    )
    registrar.commit()
    await app.start()
    await source.emit("pending")
    await started.wait()

    await registrar.aclose()
    await registrar.aclose()

    assert registrar.closed
    assert cancelled.is_set()
    assert app.bus.pending_callbacks_for("example.consumer") == 0
    await app.close()


def test_ambiguous_source_ref_requires_explicit_fan_out():
    app = BotApp(RuntimeConfig())
    app.add_source(PrototypeSource, config_key="one")
    app.add_source(PrototypeSource, config_key="two")
    registrar = ExtensionRegistrar(app, "example.consumer")

    async def handler(event: Event) -> None:
        pass

    spec = SubscriptionSpec(
        SourceRef("prototype.events"),
        PrototypeType.READY,
        handler,
    )

    with pytest.raises(SourceError, match="allow_multiple"):
        registrar.add_subscription(spec)

    handles = registrar.add_subscription(
        SubscriptionSpec(
            SourceRef("prototype.events"),
            PrototypeType.READY,
            handler,
            allow_multiple=True,
        )
    )
    assert len(handles) == 2


def test_committed_registrar_rejects_more_registration():
    app = BotApp(RuntimeConfig())
    registrar = ExtensionRegistrar(app, "example.consumer")
    registrar.commit()

    with pytest.raises(LifecycleError, match="已提交"):
        registrar.add_source(PrototypeSource)
