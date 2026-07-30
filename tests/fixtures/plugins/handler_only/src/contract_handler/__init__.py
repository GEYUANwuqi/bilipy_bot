from __future__ import annotations

import os

from butterbot.app.extensions.experimental import (
    PluginBase,
    PluginDescriptor,
    PluginRegistrar,
    SubscriptionSpec,
)
from butterbot.core.event import Event
from butterbot.core.source import SourceRef

RECEIVED: list[str] = []


class HandlerPlugin(PluginBase):
    descriptor = PluginDescriptor(
        plugin_id="contract.handler",
        version="1.0.0",
        requires_core=">=3.1.0.dev2,<4",
        requires_plugins=("contract.source",),
        provides=("contract.handler",),
    )

    async def register(self, registrar: PluginRegistrar) -> None:
        if os.environ.get("BUTTERBOT_CONTRACT_FAIL_REGISTER"):
            raise RuntimeError("external handler register failed")

        async def handle(event: Event) -> None:
            RECEIVED.append(str(event.data.value))

        registrar.add_subscription(
            SubscriptionSpec(
                source=SourceRef("contract.events", "primary"),
                status="contract.message",
                callback=handle,
            )
        )


def create_plugin() -> HandlerPlugin:
    return HandlerPlugin()


__all__ = ["RECEIVED", "create_plugin"]
