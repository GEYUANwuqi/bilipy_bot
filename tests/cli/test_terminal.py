"""全副屏终端原语测试."""

from __future__ import annotations

import pytest

from butterbot.cli import terminal


def test_full_screen_always_restores_cursor_and_primary_screen(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.setattr(terminal, "is_interactive_terminal", lambda: True)

    with pytest.raises(RuntimeError, match="boom"):
        with terminal.full_screen():
            raise RuntimeError("boom")

    output = capsys.readouterr().out
    assert output.startswith("\x1b[?1049h\x1b[?25l")
    assert output.endswith("\x1b[?25h\x1b[?1049l")


@pytest.mark.parametrize(
    ("character", "expected"),
    [
        ("\r", "enter"),
        (" ", "space"),
        ("j", "down"),
        ("K", "up"),
        ("q", "q"),
    ],
)
def test_normalize_character(character: str, expected: str):
    assert terminal._normalize_character(character) == expected
