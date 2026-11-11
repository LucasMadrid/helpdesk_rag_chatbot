from datetime import datetime
from uuid import UUID

from langchain_core.chat_history import BaseChatMessageHistory
from psycopg import AsyncConnection
from pydantic import UUID7, BaseModel

from helpdesk_rag_chatbot.adapters.chat_history import get_chat_history

_SQL_SESSION_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id uuid PRIMARY KEY,
    user_id    uuid NOT NULL,
    title      text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
"""

_SQL_CREATE_SESSION_INDEX = """
CREATE INDEX IF NOT EXISTS sessions_user_id_updated_at_idx
    ON sessions (user_id, updated_at DESC);
"""

CLAIM_SESSION = """
INSERT INTO sessions (session_id, user_id, title)
VALUES (%(session_id)s, %(user_id)s, %(title)s)
ON CONFLICT (session_id) DO UPDATE SET updated_at = now()
    WHERE sessions.user_id = EXCLUDED.user_id
RETURNING session_id
"""


class SessionNotFound(Exception):
    """The session doesn't exist, or it belongs to another user."""


class SessionSummary(BaseModel):
    session_id: UUID7
    title: str
    created_at: datetime
    updated_at: datetime


class PostgresSessionStore:
    """Sessions stored in Postgres, scoped to the connection it is given."""

    def __init__(self, conn: AsyncConnection):
        self._conn = conn

    async def open_history(
        self, session_id: UUID, user_id: UUID, title: str
    ) -> BaseChatMessageHistory:
        cur = await self._conn.execute(
            CLAIM_SESSION,
            {"session_id": session_id, "user_id": user_id, "title": title},
        )

        if await cur.fetchone() is None:
            raise SessionNotFound(session_id)
        return get_chat_history(self._conn, session_id)


async def create_session_table_and_index(conn: AsyncConnection) -> None:
    """
    Create the ``sessions`` table and its ``(user_id, updated_at DESC)`` index.

    The table and the index are created by two separate statements, each
    guarded by ``IF NOT EXISTS``, so the function is safe to call repeatedly
    and can run at every startup. The connection must use autocommit (as the
    pool in ``adapters/db.py`` does), otherwise the caller has to commit.

    :param conn: An open psycopg async connection to the app database.
    """
    await conn.execute(_SQL_SESSION_TABLE)
    await conn.execute(_SQL_CREATE_SESSION_INDEX)
