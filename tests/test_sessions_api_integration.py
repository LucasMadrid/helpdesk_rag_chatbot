"""End-to-end tests of the sessions endpoints against a real Postgres.

Every call goes through HTTP (``/chat`` and ``/sessions``) into the real
``PostgresSessionStore`` and real SQL; only the LLM is faked. Skipped unless
TEST_APP_DB_URL is set, for example the app-db container:

    TEST_APP_DB_URL=postgresql://helpdesk:<password>@localhost:5433/helpdesk \
        uv run pytest -m integration

Run only these with ``-m integration``, or leave them out with
``-m "not integration"``.
"""

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid7

import httpx
import pytest
from fakes import PromptSpy
from langchain_core.language_models import FakeListChatModel
from psycopg import AsyncConnection

from helpdesk_rag_chatbot.adapters import sessions as sessions_module
from helpdesk_rag_chatbot.adapters.chat_history import (
    CHAT_HISTORY_TABLE,
    create_chat_history_table,
)
from helpdesk_rag_chatbot.adapters.sessions import create_session_table_and_index
from helpdesk_rag_chatbot.api.dependencies import get_chat_service, get_db_connection
from helpdesk_rag_chatbot.main import create_app
from helpdesk_rag_chatbot.services.chat import ChatService

TEST_DB_URL = os.getenv("TEST_APP_DB_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.anyio,
    pytest.mark.skipif(not TEST_DB_URL, reason="TEST_APP_DB_URL is not set"),
]

LIST_LIMIT = 50


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
        await create_session_table_and_index(connection)
        yield connection


@pytest.fixture
def spy() -> PromptSpy:
    """Records each prompt the (fake) chat model receives."""
    return PromptSpy()


@pytest.fixture
async def client(
    conn: AsyncConnection, spy: PromptSpy
) -> AsyncIterator[httpx.AsyncClient]:
    """The real app over HTTP, using the test connection instead of the pool."""

    async def real_connection() -> AsyncIterator[AsyncConnection]:
        yield conn

    app = create_app()
    service = ChatService(FakeListChatModel(responses=["answer"]), callbacks=[spy])
    app.dependency_overrides[get_chat_service] = lambda: service
    app.dependency_overrides[get_db_connection] = real_connection
    # raise_app_exceptions=False: an unhandled error becomes a 500 response, as
    # it would behind a real server, instead of being re-raised into the test.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def users(conn: AsyncConnection) -> AsyncIterator[tuple[UUID, UUID]]:
    """Two fresh users; everything they created is deleted afterwards."""
    user_a, user_b = uuid7(), uuid7()
    yield user_a, user_b
    owned = "SELECT session_id FROM sessions WHERE user_id = ANY(%s::uuid[])"
    ids = [str(user_a), str(user_b)]
    await conn.execute(
        f"DELETE FROM {CHAT_HISTORY_TABLE} WHERE session_id IN ({owned})", (ids,)
    )
    await conn.execute("DELETE FROM sessions WHERE user_id = ANY(%s::uuid[])", (ids,))


async def _chat(
    client: httpx.AsyncClient, user_id: UUID, session_id: UUID, message: str = "hi"
) -> httpx.Response:
    return await client.post(
        "/chat",
        json={
            "user_id": str(user_id),
            "session_id": str(session_id),
            "message": message,
        },
    )


async def _list(client: httpx.AsyncClient, user_id: UUID) -> list[dict]:
    response = await client.get("/sessions", params={"user_id": str(user_id)})
    assert response.status_code == 200
    return response.json()


async def _delete(
    client: httpx.AsyncClient, user_id: UUID, session_id: UUID
) -> httpx.Response:
    return await client.delete(
        f"/sessions/{session_id}", params={"user_id": str(user_id)}
    )


async def _history_rows(conn: AsyncConnection, session_id: UUID) -> int:
    cursor = await conn.execute(
        f"SELECT count(*) FROM {CHAT_HISTORY_TABLE} WHERE session_id = %s",
        (str(session_id),),
    )
    row = await cursor.fetchone()
    assert row is not None
    return row[0]


async def test_owner_chats_twice_and_another_user_gets_404(
    client: httpx.AsyncClient, users: tuple[UUID, UUID]
) -> None:
    user_a, user_b = users
    session_id = uuid7()

    assert (await _chat(client, user_a, session_id)).status_code == 200
    assert (await _chat(client, user_a, session_id)).status_code == 200

    response = await _chat(client, user_b, session_id)
    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found."


async def test_list_shows_only_the_callers_sessions_newest_first(
    client: httpx.AsyncClient, users: tuple[UUID, UUID]
) -> None:
    user_a, user_b = users
    first, second = uuid7(), uuid7()
    await _chat(client, user_a, first, "How do I reset my VPN?")
    await _chat(client, user_a, second, "Printer is offline")

    listed = await _list(client, user_a)

    assert [(s["session_id"], s["title"]) for s in listed] == [
        (str(second), "Printer is offline"),
        (str(first), "How do I reset my VPN?"),
    ]
    assert await _list(client, user_b) == []

    # Chatting in the older session moves it to the top.
    await _chat(client, user_a, first, "thanks")
    assert [s["session_id"] for s in await _list(client, user_a)] == [
        str(first),
        str(second),
    ]


async def test_list_is_capped_at_the_most_recent_sessions(
    client: httpx.AsyncClient, users: tuple[UUID, UUID]
) -> None:
    user_a, _ = users
    session_ids = [uuid7() for _ in range(LIST_LIMIT + 1)]
    for session_id in session_ids:
        await _chat(client, user_a, session_id)

    listed = await _list(client, user_a)

    assert len(listed) == LIST_LIMIT
    # The oldest session is the one dropped.
    assert str(session_ids[0]) not in [s["session_id"] for s in listed]


async def test_delete_removes_the_session_and_its_history(
    client: httpx.AsyncClient, conn: AsyncConnection, users: tuple[UUID, UUID]
) -> None:
    user_a, _ = users
    session_id = uuid7()
    await _chat(client, user_a, session_id)
    assert await _history_rows(conn, session_id) > 0

    assert (await _delete(client, user_a, session_id)).status_code == 204

    assert await _list(client, user_a) == []
    assert await _history_rows(conn, session_id) == 0
    assert (await _delete(client, user_a, session_id)).status_code == 404


async def test_another_user_cannot_delete_a_session(
    client: httpx.AsyncClient, conn: AsyncConnection, users: tuple[UUID, UUID]
) -> None:
    user_a, user_b = users
    session_id = uuid7()
    await _chat(client, user_a, session_id)

    assert (await _delete(client, user_b, session_id)).status_code == 404

    assert [s["session_id"] for s in await _list(client, user_a)] == [str(session_id)]
    assert await _history_rows(conn, session_id) > 0


async def test_delete_rolls_back_the_session_if_the_history_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
    client: httpx.AsyncClient,
    conn: AsyncConnection,
    users: tuple[UUID, UUID],
) -> None:
    user_a, _ = users
    session_id = uuid7()
    await _chat(client, user_a, session_id)
    # The session delete runs first and succeeds; this statement then fails.
    monkeypatch.setattr(sessions_module, "_DELETE_HISTORY", "DELETE FROM no_such_table")

    response = await _delete(client, user_a, session_id)

    assert response.status_code == 500
    # The transaction was rolled back: nothing was deleted.
    assert [s["session_id"] for s in await _list(client, user_a)] == [str(session_id)]
    assert await _history_rows(conn, session_id) > 0
