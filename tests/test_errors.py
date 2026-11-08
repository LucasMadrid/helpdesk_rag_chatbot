"""Tests for the LLM-unavailable handler (helpdesk_rag_chatbot.api.errors)."""

import logging
from unittest.mock import AsyncMock
from uuid import uuid7

import pytest
from fastapi.testclient import TestClient
from langchain_core.exceptions import ModelAuthenticationError, ModelTimeoutError
from langchain_core.language_models import FakeListChatModel

from helpdesk_rag_chatbot.adapters.llm import LLM_UNAVAILABLE_ERRORS
from helpdesk_rag_chatbot.api.dependencies import get_chat_service
from helpdesk_rag_chatbot.main import create_app
from helpdesk_rag_chatbot.services.chat import ChatService

HEADER = "X-Request-ID"
SECRET = "https://internal-gateway.example/v1 key=sk-12345"


def make_client(error: Exception) -> TestClient:
    """Build the real app whose chat service always fails with ``error``."""
    service = ChatService(FakeListChatModel(responses=["ok"]))
    service.reply = AsyncMock(side_effect=error)  # type: ignore[method-assign]
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def chat_body() -> dict:
    return {
        "user_id": str(uuid7()),
        "session_id": str(uuid7()),
        "message": "How do I reset my password?",
    }


@pytest.mark.parametrize("error_type", LLM_UNAVAILABLE_ERRORS)
def test_llm_unavailable_errors_return_503_with_the_request_id(
    error_type: type[Exception],
) -> None:
    client = make_client(error_type(SECRET))

    response = client.post("/chat", json=chat_body())

    assert response.status_code == 503
    assert response.json()["request_id"] == response.headers[HEADER]


def test_503_body_does_not_leak_the_exception_text() -> None:
    client = make_client(ModelTimeoutError(SECRET))

    response = client.post("/chat", json=chat_body())

    assert "internal-gateway" not in response.text
    assert "sk-12345" not in response.text


def test_503_is_logged_once_at_warning_with_the_error_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = make_client(ModelTimeoutError(SECRET))

    with caplog.at_level(logging.DEBUG):
        client.post("/chat", json=chat_body())

    records = [r for r in caplog.records if r.name == "helpdesk_rag_chatbot.api.errors"]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert records[0].error_type == "ModelTimeoutError"  # type: ignore[attr-defined]
    assert records[0].exc_info is not None
    # A transient outage must not be reported as an ERROR by the middleware.
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_other_llm_errors_are_not_treated_as_unavailable() -> None:
    # Bad credentials are our bug, so they stay a 500 instead of a retryable 503.
    client = make_client(ModelAuthenticationError(SECRET))

    response = client.post("/chat", json=chat_body())

    assert response.status_code == 500
    assert SECRET not in response.text
