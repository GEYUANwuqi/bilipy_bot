from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from butterbot.core.exceptions import ConfigError
from butterbot.core.source import BaseSource

SourceFactory = Callable[..., BaseSource]


@dataclass(frozen=True, slots=True)
class SourceFactoryEntry:
    """一个已注册的 Source 构造工厂及其所有权元数据."""

    source_name: str
    factory_id: str
    factory: SourceFactory = field(repr=False)
    owner_id: str | None = None


@dataclass(frozen=True, slots=True)
class FactoryRegistration:
    """一次 Source factory 注册的不透明收据."""

    source_name: str
    factory_id: str
    owner_id: str | None
    _registry: "SourceFactoryRegistry" = field(repr=False)
    _token: object = field(repr=False)

    def unregister(self) -> bool:
        """仅在当前收据仍拥有该名称时撤销注册."""
        return self._registry.unregister(self)


class SourceFactoryRegistry:
    """按配置 builder 名称和稳定 factory ID 解析构造工厂."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, SourceFactoryEntry]] = {}
        self._tokens: dict[tuple[str, str], object] = {}

    def register(
        self,
        source_name: str,
        factory: SourceFactory,
        *,
        factory_name: str | None = None,
        owner_id: str | None = None,
    ) -> FactoryRegistration:
        """注册一个可由 YAML ``kwarg`` 选择的 Source 工厂.

        ``factory_name`` 是兼容既有 API 的参数名；其值作为稳定
        ``factory_id`` 使用，不要求等于 Python 类名。
        """
        _validate_name(source_name, "source_name")
        if not callable(factory):
            raise TypeError("factory 必须可调用")
        if owner_id is not None:
            _validate_name(owner_id, "owner_id")

        resolved_name = factory_name or getattr(factory, "__name__", None)
        _validate_name(resolved_name, "factory_name")
        assert isinstance(resolved_name, str)

        entries = self._entries.setdefault(source_name, {})
        normalized_name = resolved_name.casefold()
        if any(name.casefold() == normalized_name for name in entries):
            raise ConfigError(
                "Source 工厂 '%s.%s' 已注册" % (source_name, resolved_name)
            )
        entry = SourceFactoryEntry(
            source_name=source_name,
            factory_id=resolved_name,
            factory=factory,
            owner_id=owner_id,
        )
        token = object()
        entries[resolved_name] = entry
        self._tokens[(source_name, resolved_name)] = token
        return FactoryRegistration(
            source_name=source_name,
            factory_id=resolved_name,
            owner_id=owner_id,
            _registry=self,
            _token=token,
        )

    def unregister(self, registration: FactoryRegistration) -> bool:
        """按收据撤销 factory，旧收据不能删除后来的同名注册."""
        if registration._registry is not self:
            return False
        key = (registration.source_name, registration.factory_id)
        if self._tokens.get(key) is not registration._token:
            return False

        entries = self._entries.get(registration.source_name)
        if entries is None:
            return False
        entries.pop(registration.factory_id, None)
        self._tokens.pop(key, None)
        if not entries:
            self._entries.pop(registration.source_name, None)
        return True

    def resolve(
        self,
        source_name: str,
        factory_name: str,
    ) -> SourceFactoryEntry | None:
        """按名称查询包含 owner 的完整 factory 条目."""
        entries = self._entries.get(source_name)
        if entries is None:
            return None
        entry = entries.get(factory_name)
        if entry is not None:
            return entry

        normalized_name = factory_name.casefold()
        return next(
            (
                candidate
                for name, candidate in entries.items()
                if name.casefold() == normalized_name
            ),
            None,
        )

    def get(self, source_name: str, factory_name: str) -> SourceFactory | None:
        """按名称查询工厂；类名匹配不区分大小写以兼容环境变量覆盖."""
        entry = self.resolve(source_name, factory_name)
        return entry.factory if entry is not None else None

    def names(self, source_name: str) -> tuple[str, ...]:
        """返回某个配置 builder 可选的工厂名称."""
        return tuple(self._entries.get(source_name, ()))

    def copy(self) -> "SourceFactoryRegistry":
        """复制当前 factory 集合，后续注册互不影响."""
        registry = SourceFactoryRegistry()
        for entries in self._entries.values():
            for entry in entries.values():
                registry.register(
                    entry.source_name,
                    entry.factory,
                    factory_name=entry.factory_id,
                    owner_id=entry.owner_id,
                )
        return registry

    @classmethod
    def with_defaults(cls) -> SourceFactoryRegistry:
        """创建包含 ButterBot 内置 Source 的隔离注册表."""
        from butterbot.sources.bilibili import (
            BiliDanmakuSource,
            BiliDynamicSource,
            BiliLiveSource,
        )
        from butterbot.sources.napcat import NapcatSource

        registry = cls()
        registry.register("bilibili", BiliDanmakuSource)
        registry.register("bilibili", BiliDynamicSource)
        registry.register("bilibili", BiliLiveSource)
        registry.register("napcat", NapcatSource)
        return registry


def _validate_name(value: object, label: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("%s 必须是非空且无首尾空白的字符串" % label)
