"""Tests for the application lifespan in helpdesk_rag_chatbot.main."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from helpdesk_rag_chatbot.config import Settings
from helpdesk_rag_chatbot.main import create_app
from helpdesk_rag_chatbot.services.chat import ChatService

SettingsFactory = Callable[..., Settings]


def test_lifespan_builds_chat_service_on_startup(
    make_settings: SettingsFactory,
) -> None:
    # `with` is what runs the lifespan; a bare TestClient(app) never starts it.
    with TestClient(create_app(make_settings())) as client:
        assert isinstance(client.app.state.chat_service, ChatService)
