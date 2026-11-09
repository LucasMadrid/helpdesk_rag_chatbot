"""Tests for helpdesk_rag_chatbot.adapters.chat_history (no database needed)."""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_postgres import PostgresChatMessageHistory

from helpdesk_rag_chatbot.adapters.chat_history import (
    CHAT_HISTORY_TABLE,
    create_chat_history_table,
    get_chat_history,
)


def test_get_chat_history_returns_a_history_for_a_valid_uuid() -> None:
    # The constructor only stores its arguments, so a bare object() is enough
    # as the connection: nothing talks to Postgres until a message is read/written.
    history = get_chat_history(object(), uuid4())  # type: ignore[arg-type]

    assert isinstance(history, BaseChatMessageHistory)


def test_get_chat_history_scopes_the_history_to_the_session_as_a_string() -> None:
    session_id = uuid4()

    history = get_chat_history(object(), session_id)  # type: ignore[arg-type]

    assert isinstance(history, PostgresChatMessageHistory)
    assert history._session_id == str(session_id)


def test_create_chat_history_table_passes_the_connection_and_table_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acreate_tables = AsyncMock()
    monkeypatch.setattr(PostgresChatMessageHistory, "acreate_tables", acreate_tables)
    conn = object()

    asyncio.run(create_chat_history_table(conn))  # type: ignore[arg-type]

    acreate_tables.assert_awaited_once()
    assert acreate_tables.call_args.args == (conn, CHAT_HISTORY_TABLE)
