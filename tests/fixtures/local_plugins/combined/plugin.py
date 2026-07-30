from __future__ import annotations

from pathlib import Path

from butterbot.core.data import BaseDataMixin
from butterbot.core.event import Event
from butterbot.core.source import BaseSource
from butterbot.core.types import BaseType
from butterbot.plugin import (
    ConfigRegistrar,
    LocalPlugin,
    PluginRegistrar,
    SourceRef,
    SubscriptionSpec,
)


class CombinedType(BaseType):
    ALL = "local-combined.all"
    MESSAGE = "local-combined.message"


class CombinedData(BaseDataMixin):
    def __init__(self, value: str) -> None:
        self.value = value


class CombinedSource(BaseSource):
    source_kind = "local-combined.events"
    supported_types = CombinedType

    async def on_start(self) -> None:
        await self.ctx.bus.publish(
            self.uuid,
            Event(CombinedData("local-combined"), CombinedType.MESSAGE),
        )

    async def on_stop(self) -> None:
        pass


class CombinedPlugin(LocalPlugin):
    def register_config(self, registrar: ConfigRegistrar) -> None:
        registrar.register_builder("local-combined", dict)
        registrar.register_factory(
            "local-combined",
            CombinedSource,
            factory_id="source",
        )

    async def register(self, registrar: PluginRegistrar) -> None:
        output = Path(str(registrar.settings["output"]))

        async def handle(event: Event) -> None:
            output.write_text(str(event.data.value), encoding="utf-8")

        registrar.add_subscription(
            SubscriptionSpec(
                source=SourceRef("local-combined.events", "local-combined"),
                status="local-combined.message",
                callback=handle,
            )
        )
