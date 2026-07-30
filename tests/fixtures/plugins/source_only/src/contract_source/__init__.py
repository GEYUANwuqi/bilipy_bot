from __future__ import annotations

import os

from butterbot.app.extensions.experimental import (
    ConfigRegistrar,
    PluginBase,
    PluginDescriptor,
)
from butterbot.core.data import BaseDataMixin
from butterbot.core.event import Event
from butterbot.core.source import BaseSource
from butterbot.core.types import BaseType


class ContractType(BaseType):
    ALL = "contract.all"
    MESSAGE = "contract.message"


class ContractData(BaseDataMixin):
    def __init__(self, value: str) -> None:
        self.value = value


class ContractSource(BaseSource):
    source_kind = "contract.events"
    supported_types = ContractType

    async def on_start(self) -> None:
        if os.environ.get("BUTTERBOT_CONTRACT_FAIL_START"):
            raise RuntimeError("external source start failed")
        await self.ctx.bus.publish(
            self.uuid,
            Event(ContractData("source-only"), ContractType.MESSAGE),
        )

    async def on_stop(self) -> None:
        pass


class SourcePlugin(PluginBase):
    descriptor = PluginDescriptor(
        plugin_id="contract.source",
        version="1.0.0",
        requires_core=">=3.1.0.dev2,<4",
        provides=("contract.events",),
    )

    def register_config(self, registrar: ConfigRegistrar) -> None:
        registrar.register_builder("contract", dict)
        registrar.register_factory(
            "contract",
            ContractSource,
            factory_id="source",
        )


def create_plugin() -> SourcePlugin:
    if os.environ.get("BUTTERBOT_CONTRACT_FAIL_IMPORT"):
        raise RuntimeError("external plugin import failed")
    return SourcePlugin()


__all__ = ["ContractData", "ContractSource", "ContractType", "create_plugin"]
