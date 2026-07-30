from __future__ import annotations

from butterbot.core.data import BaseDataMixin
from butterbot.core.event import Event
from butterbot.core.source import BaseSource
from butterbot.core.types import BaseType
from butterbot.plugin import ButterPlugin, ConfigRegistrar

from .helpers import MESSAGE


class LocalContractType(BaseType):
    ALL = "local-contract.all"
    MESSAGE = "local-contract.message"


class LocalContractData(BaseDataMixin):
    def __init__(self, value: str) -> None:
        self.value = value


class LocalContractSource(BaseSource):
    source_kind = "local-contract.events"
    supported_types = LocalContractType

    async def on_start(self) -> None:
        await self.ctx.bus.publish(
            self.uuid,
            Event(LocalContractData(MESSAGE), LocalContractType.MESSAGE),
        )

    async def on_stop(self) -> None:
        pass


class SourcePlugin(ButterPlugin):
    def register_config(self, registrar: ConfigRegistrar) -> None:
        registrar.register_builder("local-contract", dict)
        registrar.register_factory(
            "local-contract",
            LocalContractSource,
            factory_id="source",
        )

    async def register(self, registrar) -> None:
        pass
