"""Tests for helpdesk_rag_chatbot.services.rag (no database or model needed)."""

from langchain_core.documents import Document

from helpdesk_rag_chatbot.services.rag import (
    Source,
    cited_sources,
    context_tokens,
    fit_docs,
    format_context,
)


def make_doc(doc_id: str, text: str) -> Document:
    return Document(
        page_content=text,
        metadata={"title": f"Title {doc_id}", "doc_id": doc_id, "version": "1.0"},
    )


def test_format_context_numbers_chunks_in_order() -> None:
    docs = [
        make_doc("vpn-setup", "Install the VPN client."),
        make_doc("printer", "Restart the printer."),
    ]

    context = format_context(docs)

    assert context == (
        "[1] Title vpn-setup vpn-setup v1.0\nInstall the VPN client.\n\n"
        "[2] Title printer printer v1.0\nRestart the printer."
    )


def test_fit_docs_keeps_top_ranked_chunks_that_fit() -> None:
    small_1 = make_doc("a", "short text " * 5)
    too_big = make_doc("b", "long text " * 200)
    small_3 = make_doc("c", "short text " * 5)
    # Room for chunks 1 and 3 together: skipping would keep [1, 3], stopping keeps [1].
    budget = context_tokens(format_context([small_1, small_3]))

    kept = fit_docs([small_1, too_big, small_3], budget)

    assert kept == [small_1]


def test_fit_docs_returns_empty_when_first_chunk_is_too_big() -> None:
    too_big = make_doc("a", "long text " * 200)
    small = make_doc("b", "short text")
    budget = context_tokens(format_context([small])) * 2

    assert fit_docs([too_big, small], budget) == []


def as_source(doc: Document) -> Source:
    meta = doc.metadata
    return Source(doc_id=meta["doc_id"], title=meta["title"], version=meta["version"])


def test_cited_sources_maps_one_based_numbers_to_chunks() -> None:
    docs = [make_doc("a", "text a"), make_doc("b", "text b"), make_doc("c", "text c")]

    sources = cited_sources("See [3] and [1].", docs)

    assert sources == [as_source(docs[2]), as_source(docs[0])]


def test_cited_sources_skips_out_of_range_numbers() -> None:
    docs = [make_doc("a", "text a"), make_doc("b", "text b"), make_doc("c", "text c")]

    # [0] must not wrap around to docs[-1] ("c"), which nothing else cites.
    sources = cited_sources("See [0], [1] and [9].", docs)

    assert sources == [as_source(docs[0])]


def test_cited_sources_lists_each_document_once() -> None:
    first_chunk = make_doc("a", "part one")
    second_chunk = make_doc("a", "part two")
    other = make_doc("b", "text b")

    sources = cited_sources(
        "See [1], [2], [3] and [1] again.", [first_chunk, second_chunk, other]
    )

    assert sources == [as_source(first_chunk), as_source(other)]
