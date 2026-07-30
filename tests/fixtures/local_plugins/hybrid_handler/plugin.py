from __future__ import annotations

from pathlib import Path

from butterbot.plugin import (
    ButterPlugin,
    Event,
    PluginRegistrar,
    SourceRef,
    SubscriptionSpec,
)


class HybridHandlerPlugin(ButterPlugin):
    def register_config(self, registrar) -> None:
        pass

    async def register(self, registrar: PluginRegistrar) -> None:
        output = Path(str(registrar.settings["output"]))

        async def handle(event: Event) -> None:
            output.write_text(str(event.data.value), encoding="utf-8")

        registrar.add_subscription(
            SubscriptionSpec(
                source=SourceRef("contract.events", "installed-primary"),
                status="contract.message",
                callback=handle,
            )
        )
