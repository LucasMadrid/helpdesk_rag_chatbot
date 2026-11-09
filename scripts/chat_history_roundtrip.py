"""Manual check: save two messages to Postgres and read them back.

Needs the app database running (``docker compose up -d app-db``) and a populated
``.env``. Run it from the repo root::

    uv run python scripts/chat_history_roundtrip.py              # new random session
    uv run python scripts/chat_history_roundtrip.py <session-id> # reuse a session

Passing the same session id on a second run shows that history survives
between processes: you will see the earlier messages plus the new two.
Messages are left in the table, so you can inspect them with psql.
"""

import asyncio
import sys
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langchain_postgres import PostgresChatMessageHistory
from psycopg import AsyncConnection

from helpdesk_rag_chatbot.adapters.chat_history import (
    CHAT_HISTORY_TABLE,
    get_chat_history,
)
from helpdesk_rag_chatbot.config import get_settings


async def main(session_id: UUID) -> int:
    settings = get_settings()
    print(f"session: {session_id}")

    async with await AsyncConnection.connect(
        settings.app_db_url.get_secret_value(), autocommit=True
    ) as conn:
        await PostgresChatMessageHistory.acreate_tables(conn, CHAT_HISTORY_TABLE)
        history = get_chat_history(conn, session_id)

        before = await history.aget_messages()
        print(f"before:  {len(before)} message(s)")

        await history.aadd_messages(
            [HumanMessage("How do I reset my password?"), AIMessage("Use the portal.")]
        )

        after = await history.aget_messages()
        for message in after:
            print(f"  {message.type:>5}: {message.content}")

    if len(after) != len(before) + 2:
        print("FAILED: expected 2 new messages")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sid = UUID(sys.argv[1]) if len(sys.argv) > 1 else uuid4()
    # psycopg's async mode cannot use Windows' default ProactorEventLoop.
    runner = asyncio.Runner(
        loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else None
    )
    with runner:
        sys.exit(runner.run(main(sid)))
