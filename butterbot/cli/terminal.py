"""Click CLI 使用的全副屏终端原语."""

from __future__ import annotations

import contextlib
import os
import select
import sys
from collections.abc import Iterator

import click

_ENTER_ALT_SCREEN = "\033[?1049h"
_LEAVE_ALT_SCREEN = "\033[?1049l"
_CLEAR_SCREEN = "\033[2J"
_CURSOR_HOME = "\033[H"
_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"


def is_interactive_terminal() -> bool:
    """判断输入和输出是否都连接到真实终端."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, OSError):
        return False


@contextlib.contextmanager
def full_screen() -> Iterator[None]:
    """进入备用屏幕并隐藏光标，离开时无条件恢复终端."""
    if not is_interactive_terminal():
        yield
        return
    sys.stdout.write(_ENTER_ALT_SCREEN + _HIDE_CURSOR)
    sys.stdout.flush()
    try:
        yield
    finally:
        sys.stdout.write(_SHOW_CURSOR + _LEAVE_ALT_SCREEN)
        sys.stdout.flush()


@contextlib.contextmanager
def prompt_mode() -> Iterator[None]:
    """在备用屏幕中暂时显示光标并清空画面，以便使用 Click prompt."""
    if not is_interactive_terminal():
        yield
        return
    sys.stdout.write(_SHOW_CURSOR + _CURSOR_HOME + _CLEAR_SCREEN)
    sys.stdout.flush()
    try:
        yield
    finally:
        sys.stdout.write(_HIDE_CURSOR)
        sys.stdout.flush()


def redraw(content: str) -> None:
    """从备用屏幕左上角整屏重绘."""
    sys.stdout.write(_CURSOR_HOME + _CLEAR_SCREEN + content)
    sys.stdout.flush()


def read_key() -> str:
    """读取单个按键，并归一化方向键、空格和 Enter."""
    if sys.platform == "win32":
        return _read_windows_key()
    return _read_posix_key()


def _read_windows_key() -> str:
    import msvcrt

    character = msvcrt.getwch()  # pyright: ignore[reportAttributeAccessIssue]
    if character in ("\x00", "\xe0"):
        code = msvcrt.getwch()  # pyright: ignore[reportAttributeAccessIssue]
        if code == "H":
            return "up"
        if code == "P":
            return "down"
        return "esc"
    return _normalize_character(character)


def _read_posix_key() -> str:
    import termios
    import tty

    descriptor = sys.stdin.fileno()
    previous = termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor)
        character = os.read(descriptor, 1)
        if character == b"\x1b":
            sequence = _read_escape_sequence(descriptor)
            if sequence in (b"[A", b"OA"):
                return "up"
            if sequence in (b"[B", b"OB"):
                return "down"
            return "esc"
        return _normalize_character(character.decode("utf-8", errors="ignore"))
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)


def _read_escape_sequence(descriptor: int) -> bytes:
    """从文件描述符读取方向键剩余字节，避开 TextIO 输入缓冲."""
    sequence = bytearray()
    while len(sequence) < 2:
        readable, _, _ = select.select([descriptor], [], [], 0.03)
        if not readable:
            break
        chunk = os.read(descriptor, 2 - len(sequence))
        if not chunk:
            break
        sequence.extend(chunk)
    return bytes(sequence)


def _normalize_character(character: str) -> str:
    if character in ("\r", "\n"):
        return "enter"
    if character == " ":
        return "space"
    if character in ("k", "K"):
        return "up"
    if character in ("j", "J"):
        return "down"
    if character == "\x03":
        raise KeyboardInterrupt
    return character


def heading(text: str) -> str:
    return click.style(text, fg="cyan", bold=True)


def success(text: str) -> str:
    return click.style(text, fg="green")


def warning(text: str) -> str:
    return click.style(text, fg="yellow")


def dim(text: str) -> str:
    return click.style(text, dim=True)


def focused(text: str) -> str:
    return click.style(text, bold=True)


def pointer() -> str:
    return click.style("❯", fg="cyan")


__all__ = [
    "dim",
    "focused",
    "full_screen",
    "heading",
    "is_interactive_terminal",
    "pointer",
    "prompt_mode",
    "read_key",
    "redraw",
    "success",
    "warning",
]
