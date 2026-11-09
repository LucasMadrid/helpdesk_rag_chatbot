from uuid import UUID

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_postgres import PostgresChatMessageHistory
from psycopg import AsyncConnection

CHAT_HISTORY_TABLE = "chat_history"


def get_chat_history(conn: AsyncConnection, session_id: UUID) -> BaseChatMessageHistory:
    """
    Build the Postgres-backed message history for one chat session.

    The connection is borrowed, not owned: the caller opens and closes it. The
    table must already exist (see ``create_chat_history_table``).

    :param conn: An open psycopg async connection to the app database.
    :param session_id: The session to read and write. Already a ``UUID``, so it is
        validated by the caller (e.g. by the request schema).
    :return: A history whose ``aadd_messages`` / ``aget_messages`` are scoped to
        ``session_id``.
    """
    return PostgresChatMessageHistory(
        CHAT_HISTORY_TABLE, str(session_id), async_connection=conn
    )


async def create_chat_history_table(conn: AsyncConnection) -> None:
    """
    Create the chat history table and its ``session_id`` index if missing.

    Safe to call repeatedly (``CREATE ... IF NOT EXISTS``), so it can run at
    every startup. The connection must use autocommit (as the pool in
    ``adapters/db.py`` does), otherwise the caller has to commit.

    :param conn: An open psycopg async connection to the app database.
    """
    await PostgresChatMessageHistory.acreate_tables(conn, CHAT_HISTORY_TABLE)
