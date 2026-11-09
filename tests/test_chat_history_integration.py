"""Integration tests for chat history against a real Postgres.

Skipped unless TEST_APP_DB_URL is set, for example the app-db container:

    TEST_APP_DB_URL=postgresql://helpdesk:<password>@localhost:5433/helpdesk \
        uv run pytest -m integration

Run only these with ``-m integration``, or leave them out with
``-m "not integration"``.
"""

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid7

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from psycopg import AsyncConnection

from helpdesk_rag_chatbot.adapters.chat_history import (
    CHAT_HISTORY_TABLE,
    create_chat_history_table,
    get_chat_history,
)

TEST_DB_URL = os.getenv("TEST_APP_DB_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.anyio,
    pytest.mark.skipif(not TEST_DB_URL, reason="TEST_APP_DB_URL is not set"),
]


@pytest.fixture
def anyio_backend() -> str:
    # psycopg's async API runs on asyncio; there is no trio driver to test.
    return "asyncio"


@pytest.fixture
async def conn() -> AsyncIterator[AsyncConnection]:
    # Autocommit, like the app's pool, so each statement commits on its own.
    async with await AsyncConnection.connect(
        TEST_DB_URL or "", autocommit=True
    ) as connection:
        await create_chat_history_table(connection)
        yield connection


@pytest.fixture
async def session_ids(conn: AsyncConnection) -> AsyncIterator[list[UUID]]:
    """Fresh session ids; their rows are deleted afterwards, pass or fail."""
    ids: list[UUID] = [uuid7(), uuid7()]
    yield ids
    await conn.execute(
        f"DELETE FROM {CHAT_HISTORY_TABLE} WHERE session_id = ANY(%s::uuid[])",
        ([str(i) for i in ids],),
    )


async def test_messages_are_read_back_in_order_with_a_new_history(
    conn: AsyncConnection, session_ids: list[UUID]
) -> None:
    session_id, _ = session_ids
    await get_chat_history(conn, session_id).aadd_messages(
        [HumanMessage("How do I reset my VPN password?"), AIMessage("Use the portal.")]
    )

    # A new object: the messages must come from Postgres, not from memory.
    messages = await get_chat_history(conn, session_id).aget_messages()

    assert [(type(m), m.content) for m in messages] == [
        (HumanMessage, "How do I reset my VPN password?"),
        (AIMessage, "Use the portal."),
    ]


async def test_another_session_reads_no_messages(
    conn: AsyncConnection, session_ids: list[UUID]
) -> None:
    session_id, other_session_id = session_ids
    await get_chat_history(conn, session_id).aadd_messages([HumanMessage("hello")])

    assert await get_chat_history(conn, other_session_id).aget_messages() == []
