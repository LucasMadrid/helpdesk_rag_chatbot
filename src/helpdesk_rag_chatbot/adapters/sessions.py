from datetime import datetime
from uuid import UUID

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage
from psycopg import AsyncConnection, sql
from psycopg.rows import class_row
from pydantic import UUID7, BaseModel

from helpdesk_rag_chatbot.adapters.chat_history import (
    CHAT_HISTORY_TABLE,
    get_chat_history,
)

_SQL_CREATE_SESSION_TABLE = """
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

_CLAIM_SESSION = """
INSERT INTO sessions (session_id, user_id, title)
VALUES (%(session_id)s, %(user_id)s, %(title)s)
ON CONFLICT (session_id) DO UPDATE SET updated_at = now()
    WHERE sessions.user_id = EXCLUDED.user_id
RETURNING session_id
"""

_LIST_SESSIONS = """
SELECT session_id, title, created_at, updated_at
FROM sessions
WHERE user_id = %s
ORDER BY updated_at DESC
LIMIT 50
"""

_DELETE_SESSION = """
DELETE FROM sessions
WHERE session_id = %s and user_id = %s
"""

_DELETE_HISTORY = sql.SQL("DELETE FROM {} WHERE session_id = %s").format(
    sql.Identifier(CHAT_HISTORY_TABLE)
)

_OWNS_SESSION = """
SELECT 1 FROM sessions WHERE session_id = %s AND user_id = %s
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
        """
        Claim the session for ``user_id`` and return its message history.

        A new session is created with ``title``. An existing session owned by
        the same user is touched (``updated_at``) and reused.

        :param session_id: The session to open.
        :param user_id: The user opening it.
        :param title: Title used only when the session is created.
        :return: The Postgres-backed history for ``session_id``.
        :raises SessionNotFound: If the session belongs to another user.
        """
        cur = await self._conn.execute(
            _CLAIM_SESSION,
            {"session_id": session_id, "user_id": user_id, "title": title},
        )

        if await cur.fetchone() is None:
            raise SessionNotFound(session_id)
        return get_chat_history(self._conn, session_id)

    async def list_sessions(self, user_id: UUID) -> list[SessionSummary]:
        """
        List the user's most recent sessions, newest activity first.

        Sessions are ordered by ``updated_at`` (descending) and capped at 50.
        Only the user's own sessions are returned, so an unknown user simply
        gets an empty list.

        :param user_id: The user whose sessions to list.
        :return: Up to 50 session summaries, most recently updated first.
        """
        async with self._conn.cursor(row_factory=class_row(SessionSummary)) as cur:
            await cur.execute(_LIST_SESSIONS, (user_id,))
            return await cur.fetchall()

    async def delete_session(self, session_id: UUID, user_id: UUID) -> None:
        """
        Delete a session and all of its chat messages.

        Both deletes run in one transaction, so the session row and its history
        are removed together or not at all. The session is deleted only if it
        belongs to ``user_id``; the history is touched only after that succeeds.

        :param session_id: The session to delete.
        :param user_id: The user who must own the session.
        :raises SessionNotFound: If the session doesn't exist or belongs to
            another user (nothing is deleted in that case).
        """
        async with self._conn.transaction():
            # Delete the session from sessions
            cur = await self._conn.execute(
                _DELETE_SESSION,
                (session_id, user_id),
            )
            if cur.rowcount == 0:
                raise SessionNotFound(session_id)
            # Delete the session from chat_history
            await self._conn.execute(_DELETE_HISTORY, (session_id,))

    async def get_messages(self, session_id: UUID, user_id: UUID) -> list[BaseMessage]:
        """
        Return the messages of one of the user's sessions, oldest first.

        :param session_id: The session to read.
        :param user_id: The user who must own the session.
        :return: The session's messages in the order they were added.
        :raises SessionNotFound: If the session doesn't exist or belongs to
            another user.
        """
        cur = await self._conn.execute(_OWNS_SESSION, (session_id, user_id))

        if await cur.fetchone() is None:
            raise SessionNotFound(session_id)

        history = get_chat_history(self._conn, session_id)
        return await history.aget_messages()


async def create_session_table_and_index(conn: AsyncConnection) -> None:
    """
    Create the ``sessions`` table and its ``(user_id, updated_at DESC)`` index.

    The table and the index are created by two separate statements, each
    guarded by ``IF NOT EXISTS``, so the function is safe to call repeatedly
    and can run at every startup. The connection must use autocommit (as the
    pool in ``adapters/db.py`` does), otherwise the caller has to commit.

    :param conn: An open psycopg async connection to the app database.
    """
    await conn.execute(_SQL_CREATE_SESSION_TABLE)
    await conn.execute(_SQL_CREATE_SESSION_INDEX)
