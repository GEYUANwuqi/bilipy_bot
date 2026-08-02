from __future__ import annotations

import os

if os.environ.get("BUTTERBOT_CONTRACT_FAIL_IMPORT"):
    raise RuntimeError("external handler import failed")

from butterbot.core.event import Event
from butterbot.plugin import (
    ButterPlugin,
    PluginDescriptor,
    register,
)

RECEIVED: list[str] = []


class ContractHandlerPlugin(ButterPlugin):
    descriptor = PluginDescriptor(
        plugin_id="contract.handler",
        version="1.0.0",
        requires_core=">=3.1.0.dev2,<4",
        requires_plugins=(),
        provides=("contract.handler",),
    )

    def source_ref(self, source_kind: str):
        if os.environ.get("BUTTERBOT_CONTRACT_FAIL_REGISTER"):
            raise RuntimeError("external handler register failed")
        return super().source_ref(source_kind)

    @register("contract.events", "contract.message")
    async def handle(self, event: Event) -> None:
        RECEIVED.append(str(event.data.value))


__all__ = ["ContractHandlerPlugin", "RECEIVED"]
