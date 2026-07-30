from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from butterbot.core.exceptions import SourceError
from butterbot.core.source import BaseSource
from butterbot.plugin.contracts.routing import SourceRef


@dataclass(frozen=True, slots=True)
class SourceCatalogEntry:
    """一个逻辑 Source 实例的控制面记录."""

    source_id: UUID
    source_kind: str
    config_key: str
    owner_id: str | None = None


class SourceCatalog:
    """把稳定逻辑 Source 引用映射到 SourceManager 的运行时 UUID."""

    def __init__(self) -> None:
        self._entries: dict[UUID, SourceCatalogEntry] = {}

    def register(
        self,
        source: BaseSource,
        *,
        owner_id: str | None = None,
    ) -> SourceCatalogEntry | None:
        """登记 Source；没有 ``source_kind`` 的 Source 不进入逻辑目录.

        为兼容既有手工组装，两个无 owner 的 Source 可以保留相同逻辑键。
        只要任一方属于插件，就拒绝相同 ``source_kind + config_key``，使插件
        consumer 在启动前得到确定绑定。
        """
        source_kind = source.source_kind
        if source_kind is None:
            return None

        entry = SourceCatalogEntry(
            source_id=source.uuid,
            source_kind=source_kind,
            config_key=source.config_key,
            owner_id=owner_id,
        )
        conflicting = tuple(
            candidate
            for candidate in self._entries.values()
            if candidate.source_kind == entry.source_kind
            and candidate.config_key == entry.config_key
        )
        if conflicting and (
            owner_id is not None
            or any(candidate.owner_id is not None for candidate in conflicting)
        ):
            conflict = conflicting[0]
            raise SourceError(
                "逻辑事件源 '%s'（config_key=%r）已由 %s 注册"
                % (
                    source_kind,
                    source.config_key,
                    conflict.owner_id or "手工应用",
                )
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

    def by_owner(self, owner_id: str) -> tuple[SourceCatalogEntry, ...]:
        """返回指定插件拥有的 Source 条目."""
        return tuple(
            entry for entry in self._entries.values() if entry.owner_id == owner_id
        )

    @property
    def entries(self) -> tuple[SourceCatalogEntry, ...]:
        """返回全部条目的稳定快照."""
        return tuple(self._entries.values())

    def clear(self) -> None:
        """清空目录."""
        self._entries.clear()
