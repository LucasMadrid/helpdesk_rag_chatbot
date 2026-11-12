"""HelpdeskClient maps the API's responses to ChatBackend types and errors."""

import base64
import json
from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid7

import httpx
import pytest

from helpdesk_rag_chatbot.ui.api_client import HelpdeskClient
from helpdesk_rag_chatbot.ui.backend import ApiError, ChatReply, Message, SessionInfo

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler) -> HelpdeskClient:
    return HelpdeskClient("http://api", transport=httpx.MockTransport(handler))


def test_chat_posts_the_request_and_returns_the_reply() -> None:
    user, session = uuid7(), uuid7()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"request_id": "rid", "answer": "hello"})

    reply = _client(handler).chat(user, session, "hi", ("image/png", b"\x89PNG"))

    assert reply == ChatReply("hello", "rid")
    assert (seen[0].method, seen[0].url.path) == ("POST", "/chat")
    assert json.loads(seen[0].content) == {
        "user_id": str(user),
        "session_id": str(session),
        "message": "hi",
        "image": {
            "media_type": "image/png",
            "data": base64.b64encode(b"\x89PNG").decode(),
        },
    }


def test_chat_without_an_image_sends_no_image_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "image" not in json.loads(request.content)
        return httpx.Response(200, json={"request_id": "rid", "answer": "ok"})

    _client(handler).chat(uuid7(), uuid7(), "hi")


def test_list_sessions_returns_session_infos() -> None:
    user, sid = uuid7(), uuid7()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sessions"
        assert request.url.params["user_id"] == str(user)
        return httpx.Response(
            200,
            json=[
                {
                    "session_id": str(sid),
                    "title": "VPN",
                    "created_at": "2026-01-01T09:00:00Z",
                    "updated_at": "2026-01-02T10:30:00Z",
                }
            ],
        )

    [info] = _client(handler).list_sessions(user)

    assert isinstance(info.session_id, UUID)
    assert isinstance(info.updated_at, datetime)
    assert info == SessionInfo(
        sid, "VPN", datetime.fromisoformat("2026-01-02T10:30:00Z")
    )


def test_get_messages_returns_messages() -> None:
    user, sid = uuid7(), uuid7()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/sessions/{sid}/messages"
        assert request.url.params["user_id"] == str(user)
        return httpx.Response(
            200,
            json=[
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "a"},
            ],
        )

    assert _client(handler).get_messages(sid, user) == [
        Message("user", "q"),
        Message("assistant", "a"),
    ]


def test_delete_session_sends_delete_and_returns_none() -> None:
    user, sid = uuid7(), uuid7()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    assert _client(handler).delete_session(sid, user) is None
    assert (seen[0].method, seen[0].url.path) == ("DELETE", f"/sessions/{sid}")
    assert seen[0].url.params["user_id"] == str(user)


def test_error_response_keeps_status_detail_and_request_id() -> None:
    rid = str(uuid7())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404, json={"detail": "Session not found.", "request_id": rid}
        )

    with pytest.raises(ApiError) as e:
        _client(handler).get_messages(uuid7(), uuid7())

    assert (e.value.status, e.value.detail, e.value.request_id) == (
        404,
        "Session not found.",
        rid,
    )


def test_validation_error_becomes_its_first_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": [
                    {"loc": ["body", "image"], "msg": "image is larger than 5 MB"},
                    {
                        "loc": ["body", "message"],
                        "msg": "String should have at least 1 character",
                    },
                ],
                "request_id": "rid",
            },
        )

    with pytest.raises(ApiError) as e:
        _client(handler).chat(uuid7(), uuid7(), "hi")

    assert (e.value.status, e.value.detail, e.value.request_id) == (
        422,
        "image is larger than 5 MB",
        "rid",
    )


def test_service_unavailable_becomes_api_error_with_detail_and_request_id() -> None:
    rid = str(uuid7())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={
                "detail": "The service is busy. Please try again.",
                "request_id": rid,
            },
        )

    with pytest.raises(ApiError) as e:
        _client(handler).chat(uuid7(), uuid7(), "hi")

    assert (e.value.status, e.value.detail, e.value.request_id) == (
        503,
        "The service is busy. Please try again.",
        rid,
    )


def test_chat_sends_the_image_as_base64_that_decodes_to_the_same_bytes() -> None:
    raw = b"\x89PNG\r\n\x1a\n" + bytes(range(256))
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"request_id": "rid", "answer": "ok"})

    _client(handler).chat(uuid7(), uuid7(), "what is this?", ("image/png", raw))

    image = seen[0]["image"]
    assert image["media_type"] == "image/png"
    assert base64.b64decode(image["data"], validate=True) == raw


def test_non_json_error_falls_back_to_the_reason_and_header_request_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            502, text="<html>bad gateway</html>", headers={"X-Request-ID": "rid"}
        )

    with pytest.raises(ApiError) as e:
        _client(handler).list_sessions(uuid7())

    assert (e.value.status, e.value.detail, e.value.request_id) == (
        502,
        "Bad Gateway",
        "rid",
    )


@pytest.mark.parametrize(
    "error", [httpx.ConnectError("down"), httpx.ReadTimeout("slow")]
)
def test_unreachable_server_raises_api_error_without_status(
    error: httpx.HTTPError,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    with pytest.raises(ApiError) as e:
        _client(handler).chat(uuid7(), uuid7(), "hi")

    assert e.value.status is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"answer": "no request id"}),
    ],
)
def test_malformed_success_body_raises_api_error(response: httpx.Response) -> None:
    with pytest.raises(ApiError) as e:
        _client(lambda request: response).chat(uuid7(), uuid7(), "hi")

    assert e.value.status == 200


def test_malformed_session_list_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"session_id": "not-a-uuid"}])

    with pytest.raises(ApiError):
        _client(handler).list_sessions(UUID(int=0))
