"""验证单个 adapter extra 的安装与导入边界."""

from __future__ import annotations

import sys
from importlib.util import find_spec


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: smoke_extra.py napcat|bilibili|all")
    extra = sys.argv[1]
    if extra not in {"napcat", "bilibili", "all"}:
        raise SystemExit("unknown extra: %s" % extra)

    assert find_spec("aiohttp") is not None
    if extra in {"napcat", "all"}:
        from butterbot.utils.websocket import AsyncWebSocketClient

        assert AsyncWebSocketClient is not None
    if extra in {"napcat", "all"}:
        from butterbot.sources.napcat import NapcatApi, NapcatSource

        assert NapcatApi is not None
        assert NapcatSource is not None
    if extra in {"bilibili", "all"}:
        assert find_spec("bilibili_api") is not None
        from butterbot.sources.bilibili import BilibiliApi, BiliDanmakuSource

        assert BiliDanmakuSource is not None
        assert BilibiliApi is not None

    print("extra smoke passed:", extra)


if __name__ == "__main__":
    main()
