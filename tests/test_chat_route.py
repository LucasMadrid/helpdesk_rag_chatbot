from collections.abc import Callable
from unittest.mock import ANY, AsyncMock
from uuid import UUID, uuid4, uuid7

import pytest
from fakes import FakeSessionStore
from fastapi.testclient import TestClient
from langchain_core.language_models import FakeListChatModel

from helpdesk_rag_chatbot.api.dependencies import get_chat_service, get_session_store
from helpdesk_rag_chatbot.main import create_app
from helpdesk_rag_chatbot.services.chat import ChatService

FAKE_ANSWER = "Reset it from the portal."

ClientFactory = Callable[..., tuple[TestClient, AsyncMock]]


@pytest.fixture
def make_client() -> ClientFactory:
    """Build a client whose chat service wraps a FakeListChatModel.

    ``service.reply`` is wrapped in an AsyncMock (it still runs the real
    service), so tests can assert whether the route called it.
    """

    def _make(store: FakeSessionStore | None = None) -> tuple[TestClient, AsyncMock]:
        service = ChatService(FakeListChatModel(responses=[FAKE_ANSWER]))
        reply = AsyncMock(wraps=service.reply)
        service.reply = reply  # type: ignore[method-assign]
        app = create_app()
        app.dependency_overrides[get_chat_service] = lambda: service
        session_store = store or FakeSessionStore()
        app.dependency_overrides[get_session_store] = lambda: session_store
        return TestClient(app), reply

    return _make


def _payload(**overrides: object) -> dict:
    body = {
        "user_id": str(uuid7()),
        "session_id": str(uuid7()),
        "message": "How do I reset my password?",
    }
    body.update(overrides)
    return body


def test_chat_returns_answer_and_request_id(make_client: ClientFactory) -> None:
    client, reply = make_client()
    body = _payload()

    response = client.post("/chat", json=body)

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == FAKE_ANSWER
    # The server generates the request_id: it must be a valid UUIDv7.
    assert UUID(data["request_id"]).version == 7
    reply.assert_awaited_once_with(
        "How do I reset my password?",
        user_id=body["user_id"],
        request_id=ANY,
        session_id=body["session_id"],
        history=ANY,
    )
    # The id given to the service (and traces) is the one returned to the client.
    assert reply.await_args.kwargs["request_id"] == data["request_id"]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        pytest.param(_payload(user_id=None), "user_id", id="null-user-id"),
        pytest.param(_payload(session_id=None), "session_id", id="null-session-id"),
        pytest.param(_payload(message=""), "message", id="empty-message"),
        pytest.param(_payload(message="   "), "message", id="blank-message"),
        pytest.param(_payload(message="x" * 1001), "message", id="message-too-long"),
        pytest.param(
            _payload(session_id=str(uuid4())), "session_id", id="session-id-not-uuid7"
        ),
        pytest.param(
            _payload(user_id="not-a-uuid"), "user_id", id="user-id-not-a-uuid"
        ),
        pytest.param(
            {k: v for k, v in _payload().items() if k != "message"},
            "message",
            id="missing-message",
        ),
        pytest.param(
            {k: v for k, v in _payload().items() if k != "user_id"},
            "user_id",
            id="missing-user-id",
        ),
        pytest.param(
            {k: v for k, v in _payload().items() if k != "session_id"},
            "session_id",
            id="missing-session-id",
        ),
    ],
)
def test_chat_rejects_invalid_payload(
    make_client: ClientFactory, body: dict, field: str
) -> None:
    client, reply = make_client()

    response = client.post("/chat", json=body)

    assert response.status_code == 422
    # Exactly one error, and it points at the offending field.
    errors = response.json()["detail"]
    assert [e["loc"] for e in errors] == [["body", field]]
    # Validation failed before the handler ran, so the service was never called.
    reply.assert_not_called()


def test_trailing_slash_redirects_to_the_canonical_path(
    make_client: ClientFactory,
) -> None:
    # FastAPI answers POST /chat/ with a 307 to /chat. 307 (not 301/302) keeps the
    # method and body, so a client that follows redirects still succeeds.
    client, reply = make_client()

    response = client.post("/chat/", json=_payload(), follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].endswith("/chat")
    reply.assert_not_called()  # the redirect never reaches the handler


def test_trailing_slash_still_works_when_the_client_follows_redirects(
    make_client: ClientFactory,
) -> None:
    client, reply = make_client()

    response = client.post("/chat/", json=_payload(), follow_redirects=True)

    assert response.status_code == 200
    assert response.json()["answer"] == FAKE_ANSWER
    reply.assert_awaited_once()


def test_chat_opens_the_session_for_the_caller_with_a_title(
    make_client: ClientFactory,
) -> None:
    store = FakeSessionStore()
    client, _ = make_client(store)
    body = _payload(message="x" * 200)

    client.post("/chat", json=body)

    assert store.calls == [(UUID(body["session_id"]), UUID(body["user_id"]), "x" * 80)]


def test_chat_returns_404_when_the_session_belongs_to_another_user(
    make_client: ClientFactory,
) -> None:
    owner_id, other_id, session_id = uuid7(), uuid7(), uuid7()
    store = FakeSessionStore()
    store.owners[session_id] = owner_id
    client, reply = make_client(store)

    response = client.post(
        "/chat", json=_payload(user_id=str(other_id), session_id=str(session_id))
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found."
    assert UUID(response.json()["request_id"]).version == 7
    reply.assert_not_called()


def test_chat_lets_the_owner_reuse_their_session(make_client: ClientFactory) -> None:
    owner_id, session_id = uuid7(), uuid7()
    client, reply = make_client()
    body = _payload(user_id=str(owner_id), session_id=str(session_id))

    first = client.post("/chat", json=body)
    second = client.post("/chat", json=body)

    assert (first.status_code, second.status_code) == (200, 200)
    assert reply.await_count == 2
