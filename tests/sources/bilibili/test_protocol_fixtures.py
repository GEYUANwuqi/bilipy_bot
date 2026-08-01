"""Bilibili 脱敏协议夹具与 fake API 回归."""

import json
from pathlib import Path
from typing import Any, cast

import pytest

from butterbot.sources.bilibili.api import bili_api
from butterbot.sources.bilibili.api.bili_api import BilibiliApi
from butterbot.sources.bilibili.data import (
    DanmakuGiftData,
    DanmakuGuardData,
    DanmakuMsgData,
    DynamicData,
)
from butterbot.sources.bilibili.data.dto import (
    DanmakuGiftDTO,
    DanmakuGuardDTO,
    DanmakuMsgDTO,
    DynamicDTO,
    LiveRoomDTO,
)

_FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "bilibili"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class _FakeUser:
    """保持上游 User 构造与异步方法形状的离线桩."""

    response: dict[str, Any] = {}
    calls: list[tuple[int, str]] = []

    def __init__(self, *, credential: Any, uid: int) -> None:
        self.uid = uid

    async def get_dynamics_new(self, offset: str = "") -> dict[str, Any]:
        self.calls.append((self.uid, offset))
        return self.response


class _FakeLiveRoom:
    response: dict[str, Any] = {}

    def __init__(
        self,
        *,
        credential: Any,
        room_display_id: int,
    ) -> None:
        self.room_display_id = room_display_id

    async def get_room_info(self) -> dict[str, Any]:
        return self.response


class TestBilibiliFixtureCorpus:
    def test_all_dynamic_shapes_parse_and_convert(self) -> None:
        raw_items = _load_fixture("dynamics.json")["items"]

        dtos = [DynamicDTO.from_raw(item) for item in raw_items]
        assert all(dto is not None for dto in dtos)
        data = [DynamicData.from_dto(dto) for dto in dtos if dto is not None]

        assert [item.dynamic_type for item in data] == [
            "DYNAMIC_TYPE_AV",
            "DYNAMIC_TYPE_DRAW",
            "DYNAMIC_TYPE_MUSIC",
            "DYNAMIC_TYPE_ARTICLE",
            "DYNAMIC_TYPE_LIVE_RCMD",
            "DYNAMIC_TYPE_FORWARD",
        ]
        assert data[0].video is not None
        assert data[0].video.bv_id == "BV1TEST00001"
        assert data[1].pics_url == [
            "https://example.invalid/pic-1.png",
            "https://example.invalid/pic-2.png",
        ]
        assert data[2].music is not None and data[2].music.music_id == "3001"
        assert data[3].article is not None and data[3].article.has_more
        assert data[4].live_rcmd is not None
        assert data[4].live_rcmd.room_id == 9001
        assert data[5].forward_orig is not None
        assert data[5].forward_orig.text == "原动态正文"

    def test_live_room_shape_parses_html_and_nested_fields(self) -> None:
        dto = LiveRoomDTO.from_raw(_load_fixture("live_room.json"))

        assert dto is not None
        assert dto.room_info.description == "第一行\n第二行 & 更多"
        assert dto.room_info.tags == ("聊天", "测试")
        assert dto.anchor_info.official_info == "测试认证"
        assert dto.notice_board is not None
        assert dto.notice_board.content == "测试公告"

    def test_danmaku_event_shapes_parse_and_convert(self) -> None:
        events = _load_fixture("danmaku_events.json")

        message_dto = DanmakuMsgDTO.from_raw(events["message"])
        gift_dto = DanmakuGiftDTO.from_raw(events["gift"])
        guard_dto = DanmakuGuardDTO.from_raw(events["guard"])

        assert message_dto is not None
        assert gift_dto is not None
        assert guard_dto is not None

        message = DanmakuMsgData.from_dto(message_dto)
        gift = DanmakuGiftData.from_dto(gift_dto)
        guard = DanmakuGuardData.from_dto(guard_dto)
        assert message.message == "测试弹幕"
        assert message.face == "https://example.invalid/user.png"
        assert message.medal is not None and message.medal.anchor_uid == 201
        assert gift.gift_name == "测试礼物"
        assert gift.blind_gift is not None
        assert gift.gift_gif == "https://example.invalid/gift.gif"
        assert guard.guard_name == "舰长"

    def test_malformed_live_recommendation_is_rejected(self) -> None:
        raw = _load_fixture("dynamics.json")["items"][4]
        raw["modules"]["module_dynamic"]["major"]["live_rcmd"]["content"] = "{"

        assert DynamicDTO.from_raw(raw) is None


class TestBilibiliFakeApi:
    @pytest.fixture(autouse=True)
    def install_fakes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _FakeUser.response = _load_fixture("dynamics.json")
        _FakeUser.calls = []
        _FakeLiveRoom.response = _load_fixture("live_room.json")
        monkeypatch.setattr(bili_api, "User", _FakeUser)
        monkeypatch.setattr(bili_api, "LiveRoom", _FakeLiveRoom)

    @pytest.mark.asyncio
    async def test_dynamic_api_uses_fixture_without_network(self) -> None:
        api = BilibiliApi(None)

        all_items = await api.get_all_dynamic(101, offset="next-page")
        newest = await api.get_new_dynamic(101)

        assert len(all_items) == 6
        assert newest.dynamic_id == "1006"
        assert newest.forward_orig is not None
        assert _FakeUser.calls == [(101, "next-page"), (101, "")]

    @pytest.mark.asyncio
    async def test_dynamic_homepage_uses_fake_function(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        response = _load_fixture("dynamics.json")

        async def fake_dynamic_page_info(credential: Any) -> dict[str, Any]:
            return response

        monkeypatch.setattr(
            bili_api,
            "get_dynamic_page_info",
            fake_dynamic_page_info,
        )
        api = BilibiliApi(cast(Any, object()))

        items = await api.get_new_dynamic_list()

        assert len(items) == 6
        assert items[0].video is not None

    @pytest.mark.asyncio
    async def test_live_room_api_uses_fixture_without_network(self) -> None:
        api = BilibiliApi(None)

        room = await api.get_room_info(9001)

        assert room.room_info.room_id == 9001
        assert room.anchor_info.name == "测试主播"
        assert room.notice_board is not None

    @pytest.mark.asyncio
    async def test_empty_dynamic_response_is_an_explicit_failure(self) -> None:
        _FakeUser.response = {"items": []}
        api = BilibiliApi(None)

        with pytest.raises(ValueError, match="未获取到动态数据"):
            await api.get_all_dynamic(101)
        with pytest.raises(ValueError, match="未获取到动态数据"):
            await api.get_new_dynamic(101)
