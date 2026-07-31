"""全副屏终端原语测试."""

from __future__ import annotations

import os
import sys
import threading
import tty

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


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX 伪终端测试")
@pytest.mark.parametrize(
    ("sequence", "expected"),
    [
        (b"\x1b[A", "up"),
        (b"\x1b[B", "down"),
        (b"\x1bOA", "up"),
        (b"\x1bOB", "down"),
    ],
)
def test_read_posix_key_reads_complete_arrow_sequence(
    sequence: bytes,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
):
    master, slave = os.openpty()
    reader = os.fdopen(slave, "r", encoding="utf-8")
    raw_mode_ready = threading.Event()
    original_setraw = tty.setraw

    def setraw(descriptor: int):
        original_setraw(descriptor)
        raw_mode_ready.set()

    def write_sequence():
        if raw_mode_ready.wait(timeout=1):
            os.write(master, sequence)

    monkeypatch.setattr(terminal.sys, "stdin", reader)
    monkeypatch.setattr(tty, "setraw", setraw)
    writer = threading.Thread(target=write_sequence)
    writer.start()
    try:
        assert terminal._read_posix_key() == expected
    finally:
        writer.join(timeout=1)
        reader.close()
        os.close(master)
