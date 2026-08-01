"""插件运行时私有注册事务回归测试."""

import asyncio

import pytest

from butterbot.app import BotApp, RuntimeConfig
from butterbot.core.data import BaseDataMixin
from butterbot.core.event import Event
from butterbot.core.exceptions import LifecycleError, SourceError
from butterbot.core.source import BaseSource
from butterbot.core.types import BaseType
from butterbot.plugin import SourceRef
from butterbot.plugin.contracts.routing import SubscriptionSpec
from butterbot.plugin.runtime._transaction import _RuntimeRegistrationTransaction
from butterbot.plugin.runtime.registrar import PluginRegistrar


class TransactionType(BaseType):
    ALL = "transaction.all"
    READY = "transaction.ready"


class TransactionData(BaseDataMixin):
    def __init__(self, value: str) -> None:
        self.value = value


class TransactionSource(BaseSource):
    source_kind = "transaction.events"
    supported_types = TransactionType

    def __init__(self, *, fail_stop: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.fail_stop = fail_stop

    async def on_start(self) -> None:
        pass

    async def on_stop(self) -> None:
        if self.fail_stop:
            raise RuntimeError("停止失败")

    async def emit(self, value: str) -> None:
        await self.ctx.bus.publish(
            self.uuid,
            Event(data=TransactionData(value=value), status=TransactionType.READY),
        )


def test_plugin_registrar_uses_private_transaction() -> None:
    assert issubclass(PluginRegistrar, _RuntimeRegistrationTransaction)


@pytest.mark.asyncio
async def test_source_and_handler_are_decoupled_by_source_ref() -> None:
    app = BotApp(RuntimeConfig())
    provider = PluginRegistrar(app, "example.provider")
    source = provider.add_source(TransactionSource, config_key="primary")
    provider.commit()

    received: asyncio.Queue[str] = asyncio.Queue()

    async def handler(event: Event) -> None:
        await received.put(event.data.value)

    consumer = PluginRegistrar(app, "example.consumer")
    handles = consumer.add_subscription(
        SubscriptionSpec(
            source=SourceRef("transaction.events", "primary"),
            status=TransactionType.READY,
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
async def test_close_cancels_only_owned_handler_after_timeout() -> None:
    app = BotApp(RuntimeConfig())
    source = app.add_source(TransactionSource, config_key="primary")
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def handler(event: Event) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    registrar = PluginRegistrar(
        app,
        "example.consumer",
        drain_timeout=0,
    )
    registrar.add_subscription(
        SubscriptionSpec(
            SourceRef("transaction.events", "primary"),
            TransactionType.READY,
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


@pytest.mark.asyncio
async def test_failed_source_removal_keeps_handle_for_retry() -> None:
    app = BotApp(RuntimeConfig())
    registrar = PluginRegistrar(app, "example.provider")
    source = registrar.add_source(TransactionSource, fail_stop=True)
    registrar.commit()
    await app.start()

    with pytest.raises(RuntimeError, match="停止失败"):
        await registrar.aclose()

    assert not registrar.closed
    assert registrar.source_ids == (source.uuid,)
    assert app.get_source(source.uuid) is source

    source.fail_stop = False
    await registrar.aclose()
    assert registrar.closed
    assert registrar.source_ids == ()
    await app.close()


@pytest.mark.asyncio
async def test_ambiguous_source_ref_requires_explicit_fan_out() -> None:
    app = BotApp(RuntimeConfig())
    app.add_source(TransactionSource, config_key="one")
    app.add_source(TransactionSource, config_key="two")
    registrar = PluginRegistrar(app, "example.consumer")

    async def handler(event: Event) -> None:
        pass

    spec = SubscriptionSpec(
        SourceRef("transaction.events"),
        TransactionType.READY,
        handler,
    )
    with pytest.raises(SourceError, match="allow_multiple"):
        registrar.add_subscription(spec)

    handles = registrar.add_subscription(
        SubscriptionSpec(
            SourceRef("transaction.events"),
            TransactionType.READY,
            handler,
            allow_multiple=True,
        )
    )
    assert len(handles) == 2
    await registrar.aclose()
    await app.close()


@pytest.mark.asyncio
async def test_committed_transaction_rejects_more_registration() -> None:
    app = BotApp(RuntimeConfig())
    registrar = PluginRegistrar(app, "example.consumer")
    registrar.commit()

    with pytest.raises(LifecycleError, match="已提交"):
        registrar.add_source(TransactionSource)

    await registrar.aclose()
    await app.close()
