"""Integration tests for the sessions store against a real Postgres.

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
from psycopg import AsyncConnection

from helpdesk_rag_chatbot.adapters.sessions import (
    PostgresSessionStore,
    SessionNotFound,
    create_session_table_and_index,
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
        await create_session_table_and_index(connection)
        yield connection


@pytest.fixture
async def session_id(conn: AsyncConnection) -> AsyncIterator[UUID]:
    """A fresh session id; its row is deleted afterwards, pass or fail."""
    new_id = uuid7()
    yield new_id
    await conn.execute("DELETE FROM sessions WHERE session_id = %s", (str(new_id),))


async def test_owner_can_open_a_session_twice_but_another_user_cannot(
    conn: AsyncConnection, session_id: UUID
) -> None:
    user_a, user_b = uuid7(), uuid7()
    store = PostgresSessionStore(conn)

    # First call claims the session, second one re-opens it as the same owner.
    await store.open_history(session_id, user_a, "title")
    await store.open_history(session_id, user_a, "title")

    with pytest.raises(SessionNotFound):
        await store.open_history(session_id, user_b, "title")
