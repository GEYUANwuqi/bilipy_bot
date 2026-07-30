import pytest

from butterbot.app import SourceFactoryRegistry
from butterbot.core.exceptions import ConfigError
from butterbot.core.source import BaseSource


class FactorySource(BaseSource):
    async def on_start(self) -> None:
        pass

    async def on_stop(self) -> None:
        pass


def test_factory_registration_tracks_owner_and_can_unregister():
    registry = SourceFactoryRegistry()

    registration = registry.register(
        "example",
        FactorySource,
        factory_name="stable",
        owner_id="example.provider",
    )
    entry = registry.resolve("example", "STABLE")

    assert entry is not None
    assert entry.factory is FactorySource
    assert entry.factory_id == "stable"
    assert entry.owner_id == "example.provider"
    assert registration.unregister()
    assert registry.resolve("example", "stable") is None
    assert not registration.unregister()


def test_stale_factory_receipt_cannot_remove_new_registration():
    registry = SourceFactoryRegistry()
    old = registry.register("example", FactorySource, factory_name="source")
    assert old.unregister()

    current = registry.register("example", FactorySource, factory_name="source")

    assert not old.unregister()
    assert registry.get("example", "source") is FactorySource
    assert current.unregister()


def test_factory_registry_copy_preserves_owner():
    registry = SourceFactoryRegistry()
    registry.register(
        "example",
        FactorySource,
        factory_name="source",
        owner_id="example.provider",
    )

    copied = registry.copy()
    entry = copied.resolve("example", "source")

    assert entry is not None
    assert entry.owner_id == "example.provider"


def test_factory_id_collision_is_case_insensitive():
    registry = SourceFactoryRegistry()
    registry.register("example", FactorySource, factory_name="Source")

    with pytest.raises(ConfigError, match="已注册"):
        registry.register("example", FactorySource, factory_name="source")
