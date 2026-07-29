from __future__ import annotations

from collections.abc import Callable

from butterbot.core.exceptions import ConfigError
from butterbot.core.source import BaseSource

SourceFactory = Callable[..., BaseSource]


class SourceFactoryRegistry:
    """按配置 builder 名称和 Source 类名解析构造工厂."""

    def __init__(self) -> None:
        self._factories: dict[str, dict[str, SourceFactory]] = {}

    def register(
        self,
        source_name: str,
        factory: SourceFactory,
        *,
        factory_name: str | None = None,
    ) -> None:
        """注册一个可由 YAML ``kwarg`` 选择的 Source 工厂."""
        _validate_name(source_name, "source_name")
        if not callable(factory):
            raise TypeError("factory 必须可调用")

        resolved_name = factory_name or getattr(factory, "__name__", None)
        _validate_name(resolved_name, "factory_name")
        assert isinstance(resolved_name, str)

        factories = self._factories.setdefault(source_name, {})
        normalized_name = resolved_name.casefold()
        if any(name.casefold() == normalized_name for name in factories):
            raise ConfigError(
                "Source 工厂 '%s.%s' 已注册" % (source_name, resolved_name)
            )
        factories[resolved_name] = factory

    def get(self, source_name: str, factory_name: str) -> SourceFactory | None:
        """按名称查询工厂；类名匹配不区分大小写以兼容环境变量覆盖."""
        factories = self._factories.get(source_name)
        if factories is None:
            return None
        factory = factories.get(factory_name)
        if factory is not None:
            return factory

        normalized_name = factory_name.casefold()
        return next(
            (
                candidate
                for name, candidate in factories.items()
                if name.casefold() == normalized_name
            ),
            None,
        )

    def names(self, source_name: str) -> tuple[str, ...]:
        """返回某个配置 builder 可选的工厂名称."""
        return tuple(self._factories.get(source_name, ()))

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
