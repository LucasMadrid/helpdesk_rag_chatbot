"""Manual demo: watch ``fit_docs`` stop at the first chunk that does not fit.

Loads the real corpus from ``data/docs``, chunks it, and treats the first
``--top-k`` chunks as if the retriever had returned them in that rank order. No
database, vector store or LLM is needed.

For each chunk it prints the chunk's own size and the cumulative size of the
formatted context so far (``[n]`` headers and separators included), then
whether ``fit_docs`` keeps it or stops there. Run it from the repo root::

    uv run python scripts/fit_docs_demo.py
    uv run python scripts/fit_docs_demo.py --budget 300 --top-k 6

Try a budget smaller than the first chunk to see an empty result.
"""

import argparse
from pathlib import Path

from helpdesk_rag_chatbot.ingestion.loaders import load_corpus
from helpdesk_rag_chatbot.services.rag import context_tokens, fit_docs, format_context
from helpdesk_rag_chatbot.splitters.registry import chunk_documents

DOCS_DIR = Path(__file__).parents[1] / "data" / "docs"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--budget", type=int, default=600, help="max context tokens")
    parser.add_argument("--top-k", type=int, default=5, help="chunks to rank")
    args = parser.parse_args()

    chunks = chunk_documents(
        load_corpus(DOCS_DIR), "recursive", CHUNK_SIZE, CHUNK_OVERLAP
    )
    ranked = chunks[: args.top_k]

    print(f"budget = {args.budget} tokens, {len(ranked)} ranked chunks\n")
    print(f"{'rank':>4}  {'doc_id':<32} {'alone':>6} {'cumul':>6}  result")

    kept_so_far = []
    stopped = False
    for rank, doc in enumerate(ranked, start=1):
        alone = context_tokens(format_context([doc]))
        cumulative = context_tokens(format_context(kept_so_far + [doc]))
        if stopped:
            result = "dropped"
        elif cumulative > args.budget:
            result = "STOP"
            stopped = True
        else:
            result = "keep"
            kept_so_far.append(doc)
        cumul_text = "" if result == "dropped" else str(cumulative)
        print(
            f"{rank:>4}  {doc.metadata['doc_id']:<32} {alone:>6} {cumul_text:>6}  {result}"
        )

    kept = fit_docs(ranked, args.budget)
    used = context_tokens(format_context(kept))
    print(f"\nfit_docs kept {len(kept)} of {len(ranked)} chunks, {used} tokens")
    assert kept == kept_so_far, "fit_docs disagrees with the table above"


if __name__ == "__main__":
    main()
