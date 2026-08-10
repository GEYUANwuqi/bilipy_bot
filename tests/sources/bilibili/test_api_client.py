"""Bilibili API 客户端选择回归测试."""

from __future__ import annotations

import bilibili_api

from butterbot.sources.bilibili.api.bili_api import _prefer_aiohttp_client


def test_prefer_aiohttp_when_curl_client_was_selected(monkeypatch) -> None:
    """安装 aiohttp 后不应继续使用存在崩溃风险的 curl WebSocket 后端."""
    selected: list[str] = []
    monkeypatch.setattr(
        bilibili_api,
        "get_registered_clients",
        lambda: {"aiohttp": object(), "curl_cffi": object()},
    )
    monkeypatch.setattr(
        bilibili_api,
        "get_selected_client",
        lambda: ("curl_cffi", object()),
    )
    monkeypatch.setattr(bilibili_api, "select_client", selected.append)

    _prefer_aiohttp_client()

    assert selected == ["aiohttp"]
