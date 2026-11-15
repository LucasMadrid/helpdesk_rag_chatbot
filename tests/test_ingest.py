"""Tests for helpdesk_rag_chatbot.ingest."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeIndex, FakePineconeClient
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.vectorstores import InMemoryVectorStore

from helpdesk_rag_chatbot.config import Settings
from helpdesk_rag_chatbot.ingest import ingest, parse_args

DOCS_DIR = Path(__file__).parents[1] / "data" / "docs"

SettingsFactory = Callable[..., Settings]


@pytest.fixture
def store() -> InMemoryVectorStore:
    """An in-memory store with a fake embedder, so no network is needed."""
    return InMemoryVectorStore(DeterministicFakeEmbedding(size=8))


def test_ingest_reports_counts(
    make_settings: SettingsFactory, store: InMemoryVectorStore
) -> None:
    report = ingest(make_settings(), FakePineconeClient(), store, DOCS_DIR)  # type: ignore[arg-type]

    assert report.splitter == "recursive"
    assert report.documents == 17
    assert report.chunks == 150
    assert report.indexed == 150
    assert len(store.store) == 150


def test_ingest_clears_before_indexing(
    make_settings: SettingsFactory, store: InMemoryVectorStore
) -> None:
    store_size_at_delete: list[int] = []

    class RecordingIndex(FakeIndex):
        def delete(self, **kwargs: Any) -> None:
            store_size_at_delete.append(len(store.store))
            super().delete(**kwargs)

    class RecordingClient(FakePineconeClient):
        def Index(self, name: str) -> FakeIndex:
            return RecordingIndex(name, self.namespaces)

    client = RecordingClient(namespaces={"recursive": 150})

    ingest(make_settings(), client, store, DOCS_DIR)  # type: ignore[arg-type]

    assert store_size_at_delete == [0]


def test_ingest_uses_chunk_settings(
    make_settings: SettingsFactory, store: InMemoryVectorStore
) -> None:
    settings = make_settings(CHUNK_SIZE=400)

    report = ingest(settings, FakePineconeClient(), store, DOCS_DIR)  # type: ignore[arg-type]

    assert report.chunks > 150


def test_parse_args_defaults_from_settings(make_settings: SettingsFactory) -> None:
    args = parse_args([], make_settings())

    assert (args.splitter, args.chunk_size, args.chunk_overlap) == (
        "recursive",
        800,
        100,
    )


def test_parse_args_overrides(make_settings: SettingsFactory) -> None:
    args = parse_args(["--chunk-size", "400", "--chunk-overlap", "50"], make_settings())

    assert args.chunk_size == 400
    assert args.chunk_overlap == 50


def test_parse_args_rejects_unknown_splitter(make_settings: SettingsFactory) -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(["--splitter", "nope"], make_settings())

    assert exc.value.code == 2
