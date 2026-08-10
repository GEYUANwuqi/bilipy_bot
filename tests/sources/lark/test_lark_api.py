import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from butterbot.sources.lark.api import LarkApi, LarkApiError, LarkConfig
from butterbot.sources.lark.api.lark_api import (
    _ManagedSdkWebSocketClient,
    _response_data,
)


class FakeResponse:
    def __init__(
        self,
        *,
        data: dict[str, Any] | None = None,
        code: int = 0,
        msg: str = "success",
    ) -> None:
        self.data = data
        self.code = code
        self.msg = msg

    def success(self) -> bool:
        return self.code == 0

    def get_log_id(self) -> str:
        return "log-id"


class FakeResource:
    def __init__(self, response: FakeResponse | None = None) -> None:
        self.requests = []
        self.response = response or FakeResponse(data={"message_id": "om_result"})

    async def acreate(self, request):
        self.requests.append(request)
        return self.response

    async def areply(self, request):
        self.requests.append(request)
        return self.response

    async def adelete(self, request):
        self.requests.append(request)
        return self.response


def _api() -> tuple[LarkApi, SimpleNamespace]:
    api = object.__new__(LarkApi)
    services = SimpleNamespace(
        message=FakeResource(),
        message_reaction=FakeResource(),
        image=FakeResource(),
        file=FakeResource(),
    )
    api._im_v1 = services
    return api, services


def test_config_validates_credentials_and_custom_events() -> None:
    config = LarkConfig(
        app_id="cli_test",
        app_secret="secret",
        custom_event_types=["contact.user.created_v3"],  # type: ignore[arg-type]
    )

    assert config.custom_event_types == ("contact.user.created_v3",)

    with pytest.raises(ValueError, match="app_id"):
        LarkConfig(app_id="", app_secret="secret")

    with pytest.raises(ValueError, match="重复内置事件"):
        LarkConfig(
            app_id="cli_test",
            app_secret="secret",
            custom_event_types=("im.message.receive_v1",),
        )


@pytest.mark.asyncio
async def test_managed_websocket_start_stop_releases_protocol_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = False
    receive_blocker = asyncio.Event()

    class FakeConnection:
        async def recv(self):
            await receive_blocker.wait()

        async def send(self, data):
            return None

        async def close(self):
            nonlocal closed
            closed = True

    async def connect(url: str, **kwargs):
        return FakeConnection()

    monkeypatch.setattr(
        "butterbot.sources.lark.api.lark_api.websockets.connect", connect
    )
    client = _ManagedSdkWebSocketClient(
        "cli_test",
        "secret",
        event_handler=object(),
    )
    monkeypatch.setattr(
        client,
        "_get_conn_url",
        lambda: "wss://example.test/ws?device_id=1&service_id=2",
    )

    await client.start_managed()
    assert client.ready

    await client.stop_managed()

    assert closed
    assert not client.ready
    assert not client._managed_tasks


@pytest.mark.asyncio
async def test_send_text_builds_create_message_request() -> None:
    api, services = _api()

    result = await api.send_text("oc_chat", "你好")

    request = services.message.requests[0]
    assert result == {"message_id": "om_result"}
    assert request.receive_id_type == "chat_id"
    assert request.request_body.receive_id == "oc_chat"
    assert request.request_body.msg_type == "text"
    assert request.request_body.content == '{"text": "你好"}'
    assert request.request_body.uuid


@pytest.mark.asyncio
async def test_reply_text_builds_reply_request() -> None:
    api, services = _api()

    await api.reply_text("om_message", "收到", reply_in_thread=True)

    request = services.message.requests[0]
    assert request.message_id == "om_message"
    assert request.request_body.reply_in_thread is True
    assert request.request_body.msg_type == "text"


@pytest.mark.asyncio
async def test_add_and_delete_reaction_use_reaction_resource() -> None:
    api, services = _api()

    await api.add_reaction("om_message", "THUMBSUP")
    await api.delete_reaction("om_message", "reaction-id")

    create_request, delete_request = services.message_reaction.requests
    assert create_request.message_id == "om_message"
    assert create_request.request_body.reaction_type.emoji_type == "THUMBSUP"
    assert delete_request.message_id == "om_message"
    assert delete_request.reaction_id == "reaction-id"


def test_failed_response_raises_lark_api_error_with_log_id() -> None:
    with pytest.raises(LarkApiError) as error:
        _response_data(FakeResponse(code=230035, msg="permission denied"))

    assert error.value.code == 230035
    assert error.value.log_id == "log-id"
    assert "permission denied" in str(error.value)
