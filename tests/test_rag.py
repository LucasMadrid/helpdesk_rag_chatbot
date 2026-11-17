"""Tests for helpdesk_rag_chatbot.services.rag (no database or model needed)."""

from langchain_core.documents import Document

from helpdesk_rag_chatbot.services.rag import format_context


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
