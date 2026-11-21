"""In-memory test doubles shared by the test modules."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.chat_history import (
    BaseChatMessageHistory,
    InMemoryChatMessageHistory,
)
from langchain_core.vectorstores import InMemoryVectorStore

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


class PromptSpy(BaseCallbackHandler):
    """Keep each prompt (list of messages) the chat model received."""

    def __init__(self) -> None:
        self.prompts: list[list] = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.prompts.append(messages[0])


class FakeIndex:
    """Stands in for ``pinecone.Index``; holds vector counts by namespace."""

    def __init__(self, name: str, namespaces: dict[str, int]) -> None:
        self.name = name
        self.namespaces = namespaces
        self.deleted: list[dict[str, Any]] = []

    def describe_index_stats(self) -> SimpleNamespace:
        return SimpleNamespace(
            namespaces={
                ns: SimpleNamespace(vector_count=count)
                for ns, count in self.namespaces.items()
            }
        )

    def delete(self, **kwargs: Any) -> None:
        self.deleted.append(kwargs)


class FakePineconeClient:
    """Stands in for ``pinecone.Pinecone``; holds index dimensions by name."""

    def __init__(
        self,
        indexes: dict[str, int] | None = None,
        namespaces: dict[str, int] | None = None,
    ) -> None:
        self.indexes = dict(indexes or {})
        self.created: list[dict[str, Any]] = []
        self.namespaces = dict(namespaces or {})
        self.opened: list[FakeIndex] = []

    def Index(self, name: str) -> FakeIndex:
        index = FakeIndex(name, self.namespaces)
        self.opened.append(index)
        return index

    def has_index(self, name: str) -> bool:
        return name in self.indexes

    def describe_index(self, name: str) -> SimpleNamespace:
        return SimpleNamespace(dimension=self.indexes[name])

    def create_index(self, **kwargs: Any) -> None:
        self.created.append(kwargs)
        self.indexes[kwargs["name"]] = kwargs["dimension"]


class ScoredInMemoryVectorStore(InMemoryVectorStore):
    """An ``InMemoryVectorStore`` that can be searched with a score threshold.

    ``InMemoryVectorStore`` has no relevance-score function, so a
    ``similarity_score_threshold`` retriever raises ``NotImplementedError`` on
    it. This one turns cosine similarity (-1 to 1) into a relevance score
    (0 to 1) with ``(s + 1) / 2``, the same mapping ``PineconeVectorStore``
    uses, so a threshold means the same thing here as in production.
    """

    def _select_relevance_score_fn(self) -> Callable[[float], float]:
        return lambda similarity: (similarity + 1) / 2


class FakeLangfuse:
    """Stands in for the Langfuse client's dataset methods, with no network.

    Like the real API, it upserts: datasets by name and items by id, so a
    second upload replaces items instead of adding copies.
    """

    def __init__(self) -> None:
        self.datasets: dict[str, dict[str, Any]] = {}
        self.items: dict[str, dict[str, dict[str, Any]]] = {}

    def create_dataset(self, *, name: str, **fields: Any) -> None:
        self.datasets[name] = fields
        self.items.setdefault(name, {})

    def create_dataset_item(self, *, dataset_name: str, id: str, **fields: Any) -> None:
        if dataset_name not in self.datasets:
            raise LookupError(f"dataset {dataset_name!r} was never created")
        self.items[dataset_name][id] = fields
