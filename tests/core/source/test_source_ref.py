import pytest

from butterbot.core.source import SourceRef


def test_source_ref_is_hashable() -> None:
    source_ref = SourceRef("example.events", "primary")

    assert {source_ref} == {SourceRef("example.events", "primary")}


@pytest.mark.parametrize(
    ("source_kind", "config_key"),
    [
        ("", None),
        (" example.events", None),
        ("example.events ", None),
        ("example.events", ""),
        ("example.events", " primary"),
    ],
)
def test_source_ref_rejects_ambiguous_empty_values(
    source_kind: str,
    config_key: str | None,
) -> None:
    with pytest.raises(ValueError):
        SourceRef(source_kind, config_key)
