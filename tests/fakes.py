"""In-memory test doubles shared by the test modules."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


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
