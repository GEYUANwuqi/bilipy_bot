from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from butterbot.core.routing import SourceRef
from butterbot.core.source import BaseSource


@dataclass(frozen=True, slots=True)
class SourceCatalogEntry:
    """一个逻辑 Source 实例的控制面记录."""

    source_id: UUID
    source_kind: str
    config_key: str


class SourceCatalog:
    """把稳定逻辑 Source 引用映射到 SourceManager 的运行时 UUID."""

    def __init__(self) -> None:
        self._entries: dict[UUID, SourceCatalogEntry] = {}

    def register(
        self,
        source: BaseSource,
    ) -> SourceCatalogEntry | None:
        """登记 Source；没有 ``source_kind`` 的 Source 不进入逻辑目录."""
        source_kind = source.source_kind
        if source_kind is None:
            return None

        entry = SourceCatalogEntry(
            source_id=source.uuid,
            source_kind=source_kind,
            config_key=source.config_key,
        )
        self._entries[source.uuid] = entry
        return entry

    def remove(self, source_id: UUID) -> SourceCatalogEntry | None:
        """移除并返回一个目录条目."""
        return self._entries.pop(source_id, None)

    def resolve(self, source_ref: SourceRef) -> tuple[UUID, ...]:
        """返回逻辑引用匹配的运行时 UUID 快照."""
        return tuple(
            entry.source_id
            for entry in self._entries.values()
            if entry.source_kind == source_ref.source_kind
            and (
                source_ref.config_key is None
                or entry.config_key == source_ref.config_key
            )
        )

    @property
    def entries(self) -> tuple[SourceCatalogEntry, ...]:
        """返回全部条目的稳定快照."""
        return tuple(self._entries.values())

    def clear(self) -> None:
        """清空目录."""
        self._entries.clear()
