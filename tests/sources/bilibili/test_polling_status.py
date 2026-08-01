"""Bilibili polling 数据状态机的离线 fake API 回归."""

from dataclasses import dataclass
from typing import Any

import pytest

from butterbot.sources.bilibili.source.bili_dynamic_source import BiliDynamicSource
from butterbot.sources.bilibili.source.bili_live_source import BiliLiveSource
from butterbot.sources.bilibili.types import DynamicType, LiveType


@dataclass(frozen=True)
class _Dynamic:
    pub_ts: int


@dataclass(frozen=True)
class _RoomInfo:
    live_status: int


@dataclass(frozen=True)
class _Live:
    room_info: _RoomInfo


class _DynamicApi:
    def __init__(self, values: list[_Dynamic]) -> None:
        self.values = iter(values)

    async def get_new_dynamic(self, uid: int) -> _Dynamic:
        return next(self.values)


class _LiveApi:
    def __init__(self, values: list[_Live]) -> None:
        self.values = iter(values)

    async def get_room_info(self, room_id: int) -> _Live:
        return next(self.values)


class _DynamicSource(BiliDynamicSource):
    def __init__(self, values: list[_Dynamic]) -> None:
        super().__init__(watch_targets=[1])
        self._fake_api = _DynamicApi(values)

    @property
    def api(self) -> Any:
        return self._fake_api


class _LiveSource(BiliLiveSource):
    def __init__(self, values: list[_Live]) -> None:
        super().__init__(watch_targets=[1])
        self._fake_api = _LiveApi(values)

    @property
    def api(self) -> Any:
        return self._fake_api


@pytest.mark.asyncio
async def test_dynamic_status_tracks_new_and_deleted_timestamps() -> None:
    source = _DynamicSource([_Dynamic(10), _Dynamic(20), _Dynamic(5)])

    await source._poll_data(1)
    assert source._get_dynamic_status(1) is DynamicType.NULL
    await source._poll_data(1)
    assert source._get_dynamic_status(1) is DynamicType.NEW
    await source._poll_data(1)
    assert source._get_dynamic_status(1) is DynamicType.DELETED


@pytest.mark.asyncio
async def test_live_status_tracks_all_transitions() -> None:
    source = _LiveSource(
        [
            _Live(_RoomInfo(0)),
            _Live(_RoomInfo(1)),
            _Live(_RoomInfo(1)),
            _Live(_RoomInfo(0)),
            _Live(_RoomInfo(0)),
        ]
    )

    expected = [
        LiveType.OFFLINE,
        LiveType.OPEN,
        LiveType.ONLINE,
        LiveType.CLOSE,
        LiveType.OFFLINE,
    ]
    actual: list[LiveType] = []
    for _ in expected:
        await source._poll_data(1)
        actual.append(source._get_live_status(1))

    assert actual == expected


@pytest.mark.parametrize("source_type", [BiliDynamicSource, BiliLiveSource])
def test_polling_configuration_rejects_invalid_interval_and_is_idempotent(
    source_type: type[BiliDynamicSource] | type[BiliLiveSource],
) -> None:
    source = source_type(poll_interval=60, watch_targets=[1])

    source.add_members([1, 2])
    source.remove_members([3, 2])
    with pytest.raises(ValueError, match="有限正数"):
        source.set_poll_interval(0)
    assert source.poll_interval == 60
    source.set_poll_interval(30)

    assert source.poll_interval == 30
    assert source.watch_targets == [1]


@pytest.mark.parametrize("interval", [0, -1, True, float("nan"), float("inf")])
@pytest.mark.parametrize("source_type", [BiliDynamicSource, BiliLiveSource])
def test_polling_constructor_rejects_invalid_interval(
    source_type: type[BiliDynamicSource] | type[BiliLiveSource],
    interval: object,
) -> None:
    with pytest.raises(ValueError, match="有限正数"):
        source_type(poll_interval=interval)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_poll_data_propagates_fake_api_error() -> None:
    source = _DynamicSource([])

    async def fail(uid: int) -> _Dynamic:
        raise RuntimeError("fake API failed")

    source._fake_api.get_new_dynamic = fail  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="fake API failed"):
        await source._poll_data(1)

    assert source._dynamic_data == {}
