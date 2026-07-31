from __future__ import annotations

from pathlib import Path

from butterbot.core.data import BaseDataMixin
from butterbot.core.event import Event
from butterbot.core.source import BaseSource
from butterbot.core.types import BaseType
from butterbot.plugin import (
    ButterPlugin,
    ConfigRegistrar,
    configure,
    register,
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


class CombinedPlugin(ButterPlugin):
    @configure
    def configure_source(self, registrar: ConfigRegistrar) -> None:
        registrar.register_builder("local-combined", dict)
        registrar.register_factory(
            "local-combined",
            CombinedSource,
            factory_id="source",
        )

    @register("local-combined.events", "local-combined.message")
    async def handle(self, event: Event) -> None:
        output = Path(str(self.settings["output"]))
        output.write_text(str(event.data.value), encoding="utf-8")
