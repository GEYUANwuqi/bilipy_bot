from __future__ import annotations

from pathlib import Path

from butterbot.core.event import Event
from butterbot.plugin import ButterPlugin, register


class LocalContractHybridHandlerPlugin(ButterPlugin):
    @register("contract.events", "contract.message")
    async def handle(self, event: Event) -> None:
        output = Path(str(self.settings["output"]))
        output.write_text(str(event.data.value), encoding="utf-8")
