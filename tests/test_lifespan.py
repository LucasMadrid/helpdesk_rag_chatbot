"""Tests for the application lifespan in helpdesk_rag_chatbot.main."""

from fastapi.testclient import TestClient

from helpdesk_rag_chatbot.config import Settings
from helpdesk_rag_chatbot.main import create_app
from helpdesk_rag_chatbot.services.chat import ChatService


def make_settings(**overrides: object) -> Settings:
    """Build validated Settings from explicit values, ignoring any real .env.

    Deterministic: Langfuse tracing is off unless a test overrides it.
    """
    base: dict[str, object] = {
        "LITELLM_URL": "http://gateway.test:4000",
        "LITELLM_KEY": "sk-test",
        "LITELLM_MODEL": "gpt-test",
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
        "LANGFUSE_BASE_URL": "http://localhost:3000",
        # Explicit, so a LANGFUSE_ENABLED in the process environment cannot leak in.
        "LANGFUSE_ENABLED": False,
        "APP_DB_URL": "postgresql://user:pw@localhost:5432/app",
    }
    # Merge as dicts: an override replaces a base value instead of raising
    # "multiple values for keyword argument".
    return Settings(_env_file=None, **(base | overrides))  # type: ignore[call-arg]


def test_lifespan_builds_chat_service_on_startup() -> None:
    # `with` is what runs the lifespan; a bare TestClient(app) never starts it.
    with TestClient(create_app(make_settings())) as client:
        assert isinstance(client.app.state.chat_service, ChatService)
