"""Tests for the application lifespan in helpdesk_rag_chatbot.main."""

from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from helpdesk_rag_chatbot import main
from helpdesk_rag_chatbot.config import Settings
from helpdesk_rag_chatbot.main import create_app
from helpdesk_rag_chatbot.services.chat import ChatService

if TYPE_CHECKING:
    from conftest import FakePool

SettingsFactory = Callable[..., Settings]


def test_lifespan_builds_chat_service_on_startup(
    make_settings: SettingsFactory, fake_pool: FakePool
) -> None:
    # `with` is what runs the lifespan; a bare TestClient(app) never starts it.
    with TestClient(create_app(make_settings())) as client:
        assert isinstance(client.app.state.chat_service, ChatService)
        assert client.app.state.app_db_pool is fake_pool


def test_lifespan_opens_pool_before_creating_table_and_closes_it(
    make_settings: SettingsFactory, fake_pool: FakePool
) -> None:
    with TestClient(create_app(make_settings())):
        pass

    assert fake_pool.events == ["open", "connection", "create_table", "close"]


def test_lifespan_closes_pool_even_if_shutdown_tracing_fails(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: SettingsFactory,
    fake_pool: FakePool,
) -> None:
    def boom(settings: Settings) -> None:
        raise RuntimeError("boom")

    # Patch `main.`, not `tracing.`: main did `from ... import shutdown_tracing`,
    # so it holds its own reference to the function and ignores a patch on the
    # module it came from.
    monkeypatch.setattr(main, "shutdown_tracing", boom)

    # Shutdown runs when the `with` block exits, so that is where boom() surfaces.
    with (
        pytest.raises(RuntimeError, match="boom"),
        TestClient(create_app(make_settings())),
    ):
        pass

    assert "close" in fake_pool.events
