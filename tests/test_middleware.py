"""Tests for the request ID middleware (helpdesk_rag_chatbot.api.middleware)."""

from unittest.mock import ANY, AsyncMock
from uuid import UUID, uuid7

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.language_models import FakeListChatModel

from helpdesk_rag_chatbot.api.dependencies import get_chat_service, get_request_id
from helpdesk_rag_chatbot.main import create_app
from helpdesk_rag_chatbot.services.chat import ChatService

HEADER = "X-Request-ID"


def make_app() -> tuple[FastAPI, AsyncMock]:
    """Build the real app with a fake chat service (no lifespan, no .env)."""
    service = ChatService(FakeListChatModel(responses=["ok"]))
    reply = AsyncMock(wraps=service.reply)
    service.reply = reply  # type: ignore[method-assign]
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    return app, reply


def chat_body(**overrides: object) -> dict:
    body = {
        "user_id": str(uuid7()),
        "session_id": str(uuid7()),
        "message": "How do I reset my password?",
    }
    body.update(overrides)
    return body


def test_response_carries_a_uuid7_request_id_header() -> None:
    app, _ = make_app()

    response = TestClient(app).get("/health")

    assert UUID(response.headers[HEADER]).version == 7


def test_each_request_gets_a_new_id() -> None:
    app, _ = make_app()
    client = TestClient(app)

    first = client.get("/health").headers[HEADER]
    second = client.get("/health").headers[HEADER]

    assert first != second


def test_header_body_and_service_share_one_id() -> None:
    app, reply = make_app()

    response = TestClient(app).post("/chat", json=chat_body())

    request_id = response.headers[HEADER]
    assert response.json()["request_id"] == request_id
    reply.assert_awaited_once_with(
        ANY, request_id=request_id, user_id=ANY, session_id=ANY
    )


def test_route_uses_the_request_id_dependency() -> None:
    # Overriding the dependency pins the ID, so the test asserts an exact value
    # instead of ANY. The middleware header is a separate, real ID.
    app, reply = make_app()
    fixed = str(uuid7())
    app.dependency_overrides[get_request_id] = lambda: fixed

    response = TestClient(app).post("/chat", json=chat_body())

    assert response.json()["request_id"] == fixed
    assert reply.await_args.kwargs["request_id"] == fixed


def test_validation_error_response_has_the_header() -> None:
    app, reply = make_app()

    response = TestClient(app).post("/chat", json=chat_body(message=""))

    assert response.status_code == 422
    assert UUID(response.headers[HEADER]).version == 7
    reply.assert_not_called()


def test_unhandled_exception_returns_500_with_the_request_id() -> None:
    # The middleware catches the exception itself and builds the 500, so the
    # client gets a JSON body and a header it can quote (no bare server 500).
    app, _ = make_app()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["request_id"] == response.headers[HEADER]
    assert "boom" not in response.text
