"""不依赖外部服务的最小完整示例."""

import asyncio
from dataclasses import dataclass

from butterbot.app import BotApp, Event, RuntimeConfig
from butterbot.core.data import BaseDataMixin
from butterbot.core.source import BaseSource
from butterbot.core.types import BaseType


class TickType(BaseType):
    """示例事件类型."""

    ALL = "tick.all"
    READY = "tick.ready"


@dataclass
class TickData(BaseDataMixin):
    """示例事件数据."""

    message: str


class TickSource(BaseSource):
    """启动后发布一次事件，并负责回收自己的后台任务."""

    supported_types = TickType

    def __init__(self) -> None:
        super().__init__()
        self._task: asyncio.Task[None] | None = None

    async def on_start(self) -> None:
        self._task = asyncio.create_task(self._publish_once())

    async def _publish_once(self) -> None:
        event = Event(data=TickData(message="ready"), status=TickType.READY)
        await self.ctx.bus.publish(self.uuid, event)

    async def on_stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def main() -> None:
    """运行应用，收到事件后通过上下文管理器正常关闭."""
    app = BotApp(RuntimeConfig())
    source = app.add_source(TickSource)
    received = asyncio.Event()

    @app.subscribe(source.uuid, TickType.READY)
    async def handle_tick(event: Event[TickData]) -> None:
        print(event.data.message)
        received.set()

    async with app:
        await asyncio.wait_for(received.wait(), timeout=1.0)


if __name__ == "__main__":
    asyncio.run(main())
