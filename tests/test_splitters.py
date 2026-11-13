"""Tests for helpdesk_rag_chatbot.splitters.registry."""

from collections import defaultdict
from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from helpdesk_rag_chatbot.ingestion.loaders import load_corpus
from helpdesk_rag_chatbot.splitters.registry import chunk_documents, get_splitter

DOCS_DIR = Path(__file__).parents[1] / "data" / "docs"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


@pytest.fixture(scope="module")
def documents() -> list[Document]:
    return load_corpus(DOCS_DIR)


@pytest.fixture(scope="module")
def chunks(documents: list[Document]) -> list[Document]:
    return chunk_documents(documents, "recursive", CHUNK_SIZE, CHUNK_OVERLAP)


def chunks_by_parent(chunks: list[Document]) -> dict[str, list[Document]]:
    grouped: dict[str, list[Document]] = defaultdict(list)
    for chunk in chunks:
        grouped[chunk.metadata["parent_id"]].append(chunk)
    return grouped


def test_get_splitter_returns_recursive() -> None:
    splitter = get_splitter("recursive", CHUNK_SIZE, CHUNK_OVERLAP)

    assert isinstance(splitter, RecursiveCharacterTextSplitter)


def test_unknown_splitter_raises() -> None:
    with pytest.raises(ValueError) as exc_info:
        get_splitter("nope", CHUNK_SIZE, CHUNK_OVERLAP)

    message = str(exc_info.value)
    assert "nope" in message
    assert "recursive" in message


def test_chunks_respect_chunk_size(
    documents: list[Document], chunks: list[Document]
) -> None:
    assert len(chunks) > len(documents)
    assert all(len(chunk.page_content) <= CHUNK_SIZE for chunk in chunks)


def test_chunks_keep_parent_metadata(
    documents: list[Document], chunks: list[Document]
) -> None:
    grouped = chunks_by_parent(chunks)

    for document in documents:
        assert grouped[document.id], f"{document.id} produced no chunks"
        for chunk in grouped[document.id]:
            assert document.metadata.items() <= chunk.metadata.items()


def test_chunks_point_to_their_parent(
    documents: list[Document], chunks: list[Document]
) -> None:
    grouped = chunks_by_parent(chunks)

    assert set(grouped) == {document.id for document in documents}
    for parent_id, parent_chunks in grouped.items():
        assert [c.metadata["chunk_index"] for c in parent_chunks] == list(
            range(len(parent_chunks))
        ), parent_id
        assert all(c.metadata["splitter"] == "recursive" for c in parent_chunks)


def test_chunking_is_deterministic(documents: list[Document]) -> None:
    def run() -> list[tuple[str, dict]]:
        return [
            (chunk.page_content, chunk.metadata)
            for chunk in chunk_documents(
                documents, "recursive", CHUNK_SIZE, CHUNK_OVERLAP
            )
        ]

    assert run() == run()


def test_chunk_metadata_is_pinecone_safe(chunks: list[Document]) -> None:
    for chunk in chunks:
        for key, value in chunk.metadata.items():
            is_scalar = isinstance(value, str | int | float | bool)
            is_str_list = isinstance(value, list) and all(
                isinstance(item, str) for item in value
            )
            assert is_scalar or is_str_list, (
                f"{chunk.metadata['parent_id']}: {key}={value!r} "
                f"({type(value).__name__})"
            )
