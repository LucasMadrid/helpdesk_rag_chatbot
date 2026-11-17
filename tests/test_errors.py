"""Tests for the LLM-unavailable handler (helpdesk_rag_chatbot.api.errors)."""

import logging
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from uuid import uuid7

import httpx
import pytest
from fakes import FakeSessionStore
from fastapi.testclient import TestClient
from langchain_core.exceptions import (
    ModelAuthenticationError,
    ModelConnectionError,
    ModelRateLimitError,
    ModelTimeoutError,
)
from langchain_core.language_models import FakeListChatModel
from openai import BadRequestError
from psycopg_pool import PoolTimeout

from helpdesk_rag_chatbot.adapters.llm import (
    LLM_UNAVAILABLE_ERRORS,
    is_content_filtered,
)
from helpdesk_rag_chatbot.api.dependencies import (
    get_chat_service,
    get_db_connection,
    get_session_store,
)
from helpdesk_rag_chatbot.api.errors import CONTENT_FILTER_REFUSAL
from helpdesk_rag_chatbot.main import create_app
from helpdesk_rag_chatbot.services.chat import ChatService

HEADER = "X-Request-ID"
SECRET = "https://internal-gateway.example/v1 key=sk-12345"

# The errors that must answer 503: the model is temporarily unreachable.
EXPECTED_UNAVAILABLE = (ModelConnectionError, ModelTimeoutError, ModelRateLimitError)


def make_client(error: Exception) -> TestClient:
    """Build the real app whose chat service always fails with ``error``."""
    service = ChatService(FakeListChatModel(responses=["ok"]))
    service.reply = AsyncMock(side_effect=error)  # type: ignore[method-assign]
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    app.dependency_overrides[get_session_store] = lambda: FakeSessionStore()
    return TestClient(app)


def chat_body() -> dict:
    return {
        "user_id": str(uuid7()),
        "session_id": str(uuid7()),
        "message": "How do I reset my password?",
    }


def test_the_unavailable_set_is_exactly_the_transient_errors() -> None:
    # The expectation is spelled out here on purpose. Parametrizing over
    # LLM_UNAVAILABLE_ERRORS alone would pass when an entry is deleted, because
    # the list of cases would shrink with it.
    assert set(LLM_UNAVAILABLE_ERRORS) == set(EXPECTED_UNAVAILABLE)


@pytest.mark.parametrize("error_type", EXPECTED_UNAVAILABLE)
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


def bad_request(message: str) -> BadRequestError:
    """Build the 400 the gateway returns, as the openai SDK raises it."""
    request = httpx.Request("POST", "http://gateway.test/v1/chat/completions")
    return BadRequestError(
        message, response=httpx.Response(400, request=request), body=None
    )


# The message LiteLLM sends when Azure's content filter blocks a prompt.
CONTENT_FILTERED = (
    "Error code: 400 - litellm.BadRequestError: litellm.ContentPolicyViolationError: "
    "The response was filtered due to the prompt triggering Azure OpenAI's content "
    "management policy."
)


def test_is_content_filtered_only_matches_content_policy_bad_requests() -> None:
    assert is_content_filtered(bad_request(CONTENT_FILTERED))
    assert not is_content_filtered(bad_request("Error code: 400 - invalid model"))
    # The marker alone is not enough: it must be a bad request from the SDK.
    assert not is_content_filtered(RuntimeError(CONTENT_FILTERED))


def test_content_filtered_message_gets_a_refusal_not_a_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = make_client(bad_request(CONTENT_FILTERED))

    with caplog.at_level(logging.DEBUG):
        response = client.post("/chat", json=chat_body())

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "request_id": response.headers[HEADER],
        "answer": CONTENT_FILTER_REFUSAL,
        "sources": [],
    }
    records = [r for r in caplog.records if r.name == "helpdesk_rag_chatbot.api.errors"]
    assert [r.levelno for r in records] == [logging.WARNING]
    assert "Azure" not in caplog.text  # the exception text is not logged
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_other_bad_requests_stay_a_500() -> None:
    client = make_client(bad_request(f"Error code: 400 - invalid model {SECRET}"))

    response = client.post("/chat", json=chat_body())

    assert response.status_code == 500
    assert SECRET not in response.text


def test_pool_timeout_returns_503_with_the_request_id_and_no_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def no_connection() -> AsyncIterator[None]:
        raise PoolTimeout(SECRET)
        yield  # makes this an async generator, like the real dependency

    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: ChatService(
        FakeListChatModel(responses=["ok"])
    )
    app.dependency_overrides[get_db_connection] = no_connection

    with caplog.at_level(logging.DEBUG):
        response = TestClient(app).post("/chat", json=chat_body())

    assert response.status_code == 503
    assert response.json()["request_id"] == response.headers[HEADER]
    assert "internal-gateway" not in response.text
    assert "sk-12345" not in response.text
    # Overload is transient: logged as a WARNING, not reported as an ERROR.
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_session_not_found_is_logged_at_info_without_a_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = FakeSessionStore()
    store.owners[session_id := uuid7()] = uuid7()
    app = create_app()
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_chat_service] = lambda: ChatService(
        FakeListChatModel(responses=["ok"])
    )

    with caplog.at_level(logging.DEBUG):
        response = TestClient(app).post(
            "/chat", json=chat_body() | {"session_id": str(session_id)}
        )

    assert response.status_code == 404
    records = [r for r in caplog.records if r.name == "helpdesk_rag_chatbot.api.errors"]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert records[0].exc_info is None
