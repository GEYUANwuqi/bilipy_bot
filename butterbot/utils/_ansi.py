"""日志 formatter 使用的最小 ANSI 能力."""

from __future__ import annotations

import ctypes
import sys


def is_ansi_supported() -> bool:
    """返回当前平台是否支持 ANSI 控制序列."""
    if not sys.platform.startswith("win"):
        return True

    try:
        from ctypes import wintypes

        version_info = sys.getwindowsversion()  # pyright: ignore[reportAttributeAccessIssue]
        kernel32 = ctypes.windll.kernel32  # pyright: ignore[reportAttributeAccessIssue]
        stdout_handle = kernel32.GetStdHandle(-11)
        if stdout_handle == wintypes.HANDLE(-1).value:
            return False
        console_mode = wintypes.DWORD()
        if not kernel32.GetConsoleMode(stdout_handle, ctypes.byref(console_mode)):
            return False
        return bool(console_mode.value & 0x0004) or version_info.major >= 10
    except (AttributeError, OSError):
        return False


def enable_ansi(mode: int = 7) -> bool:
    """在 Windows console 上启用 ANSI 控制序列."""
    if not sys.platform.startswith("win"):
        return False
    try:
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32  # pyright: ignore[reportAttributeAccessIssue]
        stdout_handle = kernel32.GetStdHandle(-11)
        if stdout_handle == wintypes.HANDLE(-1).value:
            return False
        return bool(kernel32.SetConsoleMode(stdout_handle, mode))
    except (AttributeError, OSError):
        return False


class Ansi:
    """日志格式实际使用的 ANSI 常量."""

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
