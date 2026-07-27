"""EventBus 的可重复合成负载基线，不用于声明生产吞吐."""

import argparse
import asyncio
import json
import time
import tracemalloc
from dataclasses import dataclass
from uuid import uuid4

from butterbot.core.data import BaseDataMixin
from butterbot.core.event import Event, EventBus
from butterbot.core.types import BaseType


class BenchmarkType(BaseType):
    ALL = "benchmark.all"
    EVENT = "benchmark.event"


@dataclass
class BenchmarkData(BaseDataMixin):
    sequence: int


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=10_000)
    parser.add_argument("--handlers", type=int, default=1)
    parser.add_argument("--handler-delay", type=float, default=0.001)
    parser.add_argument("--capacity", type=int)
    parser.add_argument("--close-timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.events <= 0 or args.handlers <= 0:
        parser.error("--events 和 --handlers 必须是正整数")
    if args.handler_delay < 0 or args.close_timeout < 0:
        parser.error("delay 和 timeout 不能是负数")
    if args.capacity is not None and args.capacity <= 0:
        parser.error("--capacity 必须是正整数")
    return args


async def _run(args: argparse.Namespace) -> dict[str, float | int | None]:
    bus = EventBus(max_pending_callbacks=args.capacity)
    source_id = uuid4()
    active = 0
    max_active = 0
    completed = 0

    async def handler(event: Event[BenchmarkData]) -> None:
        nonlocal active, completed, max_active
        active += 1
        max_active = max(max_active, active)
        try:
            if args.handler_delay:
                await asyncio.sleep(args.handler_delay)
        finally:
            active -= 1
            completed += 1

    for _ in range(args.handlers):
        bus.add_subscriber(
            source_id,
            handler,
            BenchmarkType.EVENT,
            BenchmarkType,
        )

    tracemalloc.start()
    publish_started = time.perf_counter()
    for sequence in range(args.events):
        await bus.publish(
            source_id,
            Event(
                data=BenchmarkData(sequence=sequence),
                status=BenchmarkType.EVENT,
            ),
        )
    publish_seconds = time.perf_counter() - publish_started
    pending_after_publish = bus.pending_callbacks

    close_started = time.perf_counter()
    await bus.close(timeout=args.close_timeout)
    close_seconds = time.perf_counter() - close_started
    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "events": args.events,
        "handlers": args.handlers,
        "handler_delay_seconds": args.handler_delay,
        "capacity": args.capacity,
        "publish_seconds": round(publish_seconds, 6),
        "close_seconds": round(close_seconds, 6),
        "pending_after_publish": pending_after_publish,
        "completed_callbacks": completed,
        "max_active_callbacks": max_active,
        "current_memory_mib": round(current_bytes / 1024 / 1024, 3),
        "peak_memory_mib": round(peak_bytes / 1024 / 1024, 3),
    }


def main() -> None:
    args = _parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
