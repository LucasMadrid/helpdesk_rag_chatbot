"""Manual demo: see which sources ``cited_sources`` pulls out of an answer.

Picks three real chunks from ``data/docs``: two from the same document and one
from another, in that rank order, as if the retriever had returned them. Then
runs a few hand-written answers through ``cited_sources``. No database, vector
store or LLM is needed. Run it from the repo root::

    uv run python scripts/cited_sources_demo.py

Each case prints the answer, the sources it should give, and what
``cited_sources`` returned, as (doc_id, [n] numbers) pairs, with OK or
MISMATCH.
"""

from pathlib import Path

from langchain_core.documents import Document

from helpdesk_rag_chatbot.ingestion.loaders import load_corpus
from helpdesk_rag_chatbot.services.rag import cited_sources, format_context
from helpdesk_rag_chatbot.splitters.registry import chunk_documents

DOCS_DIR = Path(__file__).parents[1] / "data" / "docs"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def pick_docs() -> list[Document]:
    chunks = chunk_documents(
        load_corpus(DOCS_DIR), "recursive", CHUNK_SIZE, CHUNK_OVERLAP
    )
    first, second = chunks[0], chunks[1]
    other = next(c for c in chunks if c.metadata["doc_id"] != first.metadata["doc_id"])
    assert second.metadata["doc_id"] == first.metadata["doc_id"], (
        "want two chunks of one doc"
    )
    return [first, second, other]


def main() -> None:
    docs = pick_docs()
    a, b = docs[0].metadata["doc_id"], docs[2].metadata["doc_id"]  # [1], [2] share a

    print("Context headers:")
    for line in format_context(docs).splitlines():
        if line.startswith("["):
            print(f"  {line}")
    print()

    # Each expected source is (doc_id, the [n] markers that point to it).
    cases = [
        ("one citation", "Call the service desk [1].", [(a, (1,))]),
        ("two documents", "Call the desk [1], then see [3].", [(a, (1,)), (b, (3,))]),
        ("same doc twice ([1] and [2])", "See [1] and [2].", [(a, (1, 2))]),
        ("repeated number", "See [3]. As said in [3]...", [(b, (3,))]),
        ("order of first mention", "See [3] and [1].", [(b, (3,)), (a, (1,))]),
        ("out of range [9]", "See [1] and [9].", [(a, (1,))]),
        ("zero is not a chunk", "See [0].", []),
        ("no citations", "I don't know.", []),
    ]

    failures = 0
    for name, answer, expected in cases:
        got = [(s.doc_id, s.numbers) for s in cited_sources(answer, docs)]
        ok = got == expected
        failures += not ok
        print(f"{'OK      ' if ok else 'MISMATCH'} {name}: {answer!r}")
        print(f"         expected {expected}")
        print(f"         got      {got}")

    print(f"\n{len(cases) - failures} of {len(cases)} cases OK")


if __name__ == "__main__":
    main()
