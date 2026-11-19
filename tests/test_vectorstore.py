"""Tests for helpdesk_rag_chatbot.adapters.vectorstore."""

from hashlib import sha256
from pathlib import Path

import pytest
from fakes import FakePineconeClient, ScoredInMemoryVectorStore
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.vectorstores import InMemoryVectorStore

from helpdesk_rag_chatbot.adapters.vectorstore import (
    CURRENT_ONLY_FILTER,
    chunk_id,
    clear_namespace,
    ensure_index,
    get_retriever,
    index_chunks,
)
from helpdesk_rag_chatbot.ingestion.loaders import load_corpus
from helpdesk_rag_chatbot.splitters.registry import chunk_documents

DOCS_DIR = Path(__file__).parents[1] / "data" / "docs"


@pytest.fixture(scope="module")
def corpus_chunks() -> list[Document]:
    """The real corpus, split with the default settings (150 chunks)."""
    return chunk_documents(load_corpus(DOCS_DIR), "recursive", 800, 100)


@pytest.fixture
def store() -> InMemoryVectorStore:
    """An in-memory store with a fake embedder, so no network is needed.

    It has relevance scores, so the score-threshold retriever works on it.
    """
    return ScoredInMemoryVectorStore(DeterministicFakeEmbedding(size=8))


def _chunk(text: str = "Restart the VPN client.", index: int = 3) -> Document:
    """Build a chunk with the metadata the splitter adds."""
    return Document(
        page_content=text,
        metadata={"parent_id": "vpn-setup@2", "chunk_index": index},
    )


def test_chunk_id_has_parent_index_and_content_hash() -> None:
    text = "Restart the VPN client."
    expected_hash = sha256(text.encode("utf-8")).hexdigest()[:16]

    assert chunk_id(_chunk(text)) == f"vpn-setup@2#3#{expected_hash}"


def test_chunk_id_is_stable_for_the_same_chunk() -> None:
    assert chunk_id(_chunk()) == chunk_id(_chunk())


def test_chunk_id_changes_when_content_changes() -> None:
    assert chunk_id(_chunk("Restart the VPN client.")) != chunk_id(
        _chunk("Reinstall the VPN client.")
    )


def test_chunk_ids_unique_across_corpus(corpus_chunks: list[Document]) -> None:
    ids = [chunk_id(c) for c in corpus_chunks]

    assert len(ids) == 150
    assert len(set(ids)) == 150
    # Pinecone record IDs must be ASCII and at most 512 characters.
    assert all(i.isascii() and len(i) <= 512 for i in ids)


def test_index_chunks_twice_does_not_duplicate(
    store: InMemoryVectorStore, corpus_chunks: list[Document]
) -> None:
    first = index_chunks(store, corpus_chunks)
    second = index_chunks(store, corpus_chunks)

    assert len(corpus_chunks) == 150
    assert first == second == [chunk_id(c) for c in corpus_chunks]
    assert len(store.store) == 150


def test_indexed_chunk_keeps_metadata(
    store: InMemoryVectorStore, corpus_chunks: list[Document]
) -> None:
    ids = index_chunks(store, corpus_chunks)

    [stored] = store.get_by_ids([ids[0]])

    assert stored.page_content == corpus_chunks[0].page_content
    assert stored.metadata == corpus_chunks[0].metadata


def test_index_chunks_with_no_chunks_returns_empty(
    store: InMemoryVectorStore,
) -> None:
    assert index_chunks(store, []) == []
    assert store.store == {}


def test_ensure_index_creates_missing_index() -> None:
    client = FakePineconeClient()

    ensure_index(client, "helpdesk-corpus", 1536)  # type: ignore[arg-type]

    assert len(client.created) == 1
    created = client.created[0]
    assert created["name"] == "helpdesk-corpus"
    assert created["dimension"] == 1536
    assert created["metric"] == "cosine"


def test_ensure_index_leaves_matching_index_alone() -> None:
    client = FakePineconeClient({"helpdesk-corpus": 1536})

    ensure_index(client, "helpdesk-corpus", 1536)  # type: ignore[arg-type]

    assert client.created == []


def test_ensure_index_rejects_dimension_mismatch() -> None:
    client = FakePineconeClient({"helpdesk-corpus": 768})

    with pytest.raises(ValueError, match="dimension 768.*produces 1536"):
        ensure_index(client, "helpdesk-corpus", 1536)  # type: ignore[arg-type]

    assert client.created == []


def test_clear_namespace_deletes_existing() -> None:
    client = FakePineconeClient(namespaces={"recursive": 150, "markdown": 90})

    cleared = clear_namespace(client, "helpdesk-corpus", "recursive")  # type: ignore[arg-type]

    assert cleared == 150
    [index] = client.opened
    assert index.name == "helpdesk-corpus"
    assert index.deleted == [{"delete_all": True, "namespace": "recursive"}]


def test_clear_namespace_skips_missing() -> None:
    client = FakePineconeClient(namespaces={"markdown": 90})

    cleared = clear_namespace(client, "helpdesk-corpus", "recursive")  # type: ignore[arg-type]

    assert cleared == 0
    [index] = client.opened
    assert index.deleted == []


def _current_only(doc: Document) -> bool:
    """In-memory twin of ``CURRENT_ONLY_FILTER``, which only Pinecone reads."""
    return doc.metadata["status"] == "current"


def _current_chunk(text: str, index: int = 0) -> Document:
    """Build a chunk that ``_current_only`` lets through."""
    chunk = _chunk(text, index)
    chunk.metadata["status"] = "current"
    return chunk


def test_get_retriever_passes_k_and_filter(store: InMemoryVectorStore) -> None:
    retriever = get_retriever(store, 4, CURRENT_ONLY_FILTER, min_score=0.0)

    assert retriever.search_kwargs == {
        "k": 4,
        "score_threshold": 0.0,
        "filter": {"status": {"$eq": "current"}},
    }


def test_retriever_drops_superseded_twin(store: InMemoryVectorStore) -> None:
    text = "Remote work needs manager approval."
    twins = [
        Document(
            page_content=text,
            metadata={
                "parent_id": f"hr-remote-work-policy@{version}",
                "chunk_index": 0,
                "status": status,
                "version": version,
            },
        )
        for version, status in [("1.0", "superseded"), ("2.0", "current")]
    ]
    index_chunks(store, twins)

    docs = get_retriever(store, 4, _current_only, min_score=0.0).invoke(text)

    assert [d.metadata["version"] for d in docs] == ["2.0"]


def test_retriever_returns_at_most_k(
    store: InMemoryVectorStore, corpus_chunks: list[Document]
) -> None:
    index_chunks(store, corpus_chunks)

    docs = get_retriever(store, 3, _current_only, min_score=0.0).invoke(
        "How do I reset my password?"
    )

    assert len(docs) == 3


def test_retriever_on_corpus_has_no_superseded(
    store: InMemoryVectorStore, corpus_chunks: list[Document]
) -> None:
    index_chunks(store, corpus_chunks)

    docs = get_retriever(store, 150, _current_only, min_score=0.0).invoke(
        "remote work policy"
    )

    assert len(docs) == 136
    assert all(d.metadata["status"] == "current" for d in docs)


def test_get_retriever_uses_the_score_threshold(store: InMemoryVectorStore) -> None:
    retriever = get_retriever(store, 4, CURRENT_ONLY_FILTER, min_score=0.4)

    assert retriever.search_type == "similarity_score_threshold"
    assert retriever.search_kwargs["score_threshold"] == 0.4


def test_retriever_drops_chunks_below_min_score(store: InMemoryVectorStore) -> None:
    # The fake embedder gives the same text the same vector, so the exact match
    # scores 1.0 and the others score lower.
    question = "How do I reset my password?"
    texts = [question, "The canteen opens at noon.", "Book a meeting room."]
    index_chunks(
        store,
        [_current_chunk(text, index=i) for i, text in enumerate(texts)],
    )

    docs = get_retriever(store, 4, _current_only, min_score=0.99).invoke(question)

    assert [d.page_content for d in docs] == [question]


def test_retriever_returns_nothing_when_no_chunk_clears_min_score(
    store: InMemoryVectorStore,
) -> None:
    index_chunks(store, [_current_chunk("The canteen opens at noon.")])

    docs = get_retriever(store, 4, _current_only, min_score=0.99).invoke(
        "How do I reset my password?"
    )

    assert docs == []
