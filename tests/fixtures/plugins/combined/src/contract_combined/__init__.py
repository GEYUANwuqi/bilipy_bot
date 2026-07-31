from __future__ import annotations

from butterbot.core.data import BaseDataMixin
from butterbot.core.event import Event
from butterbot.core.source import BaseSource
from butterbot.core.types import BaseType
from butterbot.plugin import (
    ButterPlugin,
    ConfigRegistrar,
    PluginDescriptor,
    configure,
    register,
)

RECEIVED: list[str] = []


class CombinedType(BaseType):
    ALL = "combined.all"
    MESSAGE = "combined.message"


class CombinedData(BaseDataMixin):
    def __init__(self, value: str) -> None:
        self.value = value


class CombinedSource(BaseSource):
    source_kind = "combined.events"
    supported_types = CombinedType

    async def on_start(self) -> None:
        await self.ctx.bus.publish(
            self.uuid,
            Event(CombinedData("combined"), CombinedType.MESSAGE),
        )

    async def on_stop(self) -> None:
        pass


class CombinedPlugin(ButterPlugin):
    descriptor = PluginDescriptor(
        plugin_id="contract.combined",
        version="1.0.0",
        requires_core=">=3.1.0.dev2,<4",
        provides=("combined.events", "combined.handler"),
    )

    @configure
    def configure_source(self, registrar: ConfigRegistrar) -> None:
        registrar.register_builder("combined", dict)
        registrar.register_factory(
            "combined",
            CombinedSource,
            factory_id="source",
        )

    @register("combined.events", "combined.message")
    async def handle(self, event: Event) -> None:
        RECEIVED.append(str(event.data.value))


__all__ = ["CombinedPlugin", "RECEIVED"]
