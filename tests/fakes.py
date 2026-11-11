"""In-memory test doubles shared by the test modules."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from langchain_core.chat_history import (
    BaseChatMessageHistory,
    InMemoryChatMessageHistory,
)

from helpdesk_rag_chatbot.adapters.sessions import SessionNotFound


class FakePool:
    """Stands in for AsyncConnectionPool, so no database is needed.

    ``events`` records the calls in order, so a test can assert on the sequence.
    """

    def __init__(self) -> None:
        self.events: list[str] = []

    async def open(self, wait: bool = False, timeout: float = 30.0) -> None:
        self.events.append("open")

    async def close(self, timeout: float = 5.0) -> None:
        self.events.append("close")

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[object]:
        self.events.append("connection")
        yield object()


class FakeSessionStore:
    """Stands in for PostgresSessionStore, so no database is needed.

    Behaves like the real claim: the first user to open a session owns it, and
    another user opening it gets ``SessionNotFound``. ``owners`` maps
    ``session_id`` to ``user_id`` and can be pre-filled by a test. ``calls``
    records each ``open_history`` call as ``(session_id, user_id, title)``.
    """

    def __init__(self) -> None:
        self.owners: dict[UUID, UUID] = {}
        self.calls: list[tuple[UUID, UUID, str]] = []

    async def open_history(
        self, session_id: UUID, user_id: UUID, title: str
    ) -> BaseChatMessageHistory:
        self.calls.append((session_id, user_id, title))
        if self.owners.setdefault(session_id, user_id) != user_id:
            raise SessionNotFound(str(session_id))
        return InMemoryChatMessageHistory()
