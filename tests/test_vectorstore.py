"""Tests for helpdesk_rag_chatbot.adapters.vectorstore."""

from hashlib import sha256
from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.documents import Document

from helpdesk_rag_chatbot.adapters.vectorstore import chunk_id, ensure_index


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


class FakePineconeClient:
    """Stands in for ``pinecone.Pinecone``; holds index dimensions by name."""

    def __init__(self, indexes: dict[str, int] | None = None) -> None:
        self.indexes = dict(indexes or {})
        self.created: list[dict[str, Any]] = []

    def has_index(self, name: str) -> bool:
        return name in self.indexes

    def describe_index(self, name: str) -> SimpleNamespace:
        return SimpleNamespace(dimension=self.indexes[name])

    def create_index(self, **kwargs: Any) -> None:
        self.created.append(kwargs)
        self.indexes[kwargs["name"]] = kwargs["dimension"]


def test_ensure_index_creates_missing_index() -> None:
    client = FakePineconeClient()

    ensure_index(client, "helpdesk-docs", 1536)  # type: ignore[arg-type]

    assert len(client.created) == 1
    created = client.created[0]
    assert created["name"] == "helpdesk-docs"
    assert created["dimension"] == 1536
    assert created["metric"] == "cosine"


def test_ensure_index_leaves_matching_index_alone() -> None:
    client = FakePineconeClient({"helpdesk-docs": 1536})

    ensure_index(client, "helpdesk-docs", 1536)  # type: ignore[arg-type]

    assert client.created == []


def test_ensure_index_rejects_dimension_mismatch() -> None:
    client = FakePineconeClient({"helpdesk-docs": 768})

    with pytest.raises(ValueError, match="dimension 768.*produces 1536"):
        ensure_index(client, "helpdesk-docs", 1536)  # type: ignore[arg-type]

    assert client.created == []
