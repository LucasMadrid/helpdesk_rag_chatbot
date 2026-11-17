import re
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.messages import SystemMessage
from langchain_core.messages.utils import count_tokens_approximately


@dataclass(frozen=True)
class Source:
    """
    A document cited in an answer, identified by its id and version.

    :ivar doc_id: The document's stable id, e.g. ``hr-remote-work-policy``.
    :ivar title: The document's human-readable title.
    :ivar version: The document's version, e.g. ``2.0``.
    """

    doc_id: str
    title: str
    version: str


def format_context(docs: list[Document]) -> str:
    """
    Render retrieved chunks as numbered context blocks for the prompt.

    Each block is a header line ``[n] <title> (<doc_id> v<version>)`` followed
    by the chunk text. Numbers start at 1 and follow the order of ``docs``, so
    the model can cite a chunk as ``[n]``. Blocks are separated by a blank line.

    :param docs: Retrieved chunks; each needs ``title``, ``doc_id`` and
        ``version`` in its metadata.
    :return: The formatted context, or an empty string if ``docs`` is empty.
    :raises KeyError: If a chunk's metadata lacks one of the required keys.
    """
    blocks = []
    for index, doc in enumerate(docs, start=1):
        meta = doc.metadata
        header = f"[{index}] {meta['title']} ({meta['doc_id']} v{meta['version']})"

        blocks.append(f"{header}\n{doc.page_content}")

    return "\n\n".join(blocks)


def context_tokens(context: str) -> int:
    """
    Count the tokens in a formatted context, approximately.

    Used to keep the context within ``CONTEXT_MAX_TOKENS``.

    :param context: The text returned by ``format_context``.
    :return: The approximate token count.
    """

    return count_tokens_approximately(messages=[SystemMessage(context)])


def fit_docs(docs: list[Document], max_tokens: int) -> list[Document]:
    """
    Keep the top-ranked chunks whose formatted context fits the token budget.

    Chunks are added in rank order, and each step counts the whole formatted
    context (``[n]`` headers and separators included), not one chunk alone.
    It stops at the first chunk that would go over ``max_tokens`` and never
    skips ahead, so the result is always the first N chunks of ``docs``.

    :param docs: Retrieved chunks, best match first.
    :param max_tokens: The most tokens the formatted context may use.
    :return: The longest prefix of ``docs`` that fits; empty if the first
        chunk alone is too big.
    """
    kept: list[Document] = []

    for doc in docs:
        tokens = context_tokens(format_context(kept + [doc]))
        if tokens > max_tokens:
            break
        kept.append(doc)

    return kept


def cited_sources(answer: str, docs: list[Document]) -> list[Source]:
    """
    List the documents an answer cites with ``[n]`` markers.

    ``[n]`` refers to the n-th chunk of ``docs``, numbered from 1 as in
    ``format_context``. Numbers outside ``1..len(docs)`` (``[0]`` included) are
    skipped. Several chunks of one document, or one number cited more than
    once, give a single source, identified by ``doc_id`` and ``version``.

    :param answer: The model's answer text.
    :param docs: The chunks sent as context, in the order they were numbered.
    :return: The cited sources in order of first mention; empty if the answer
        cites nothing valid.
    :raises KeyError: If a cited chunk's metadata lacks ``doc_id``, ``title``
        or ``version``.
    """
    sources: list[Source] = []
    seen: set[tuple[str, str]] = set()

    for number in re.findall(r"\[(\d+)\]", answer):
        n = int(number)

        if not 1 <= n <= len(docs):
            continue

        meta = docs[n - 1].metadata

        key = (meta["doc_id"], meta["version"])

        if key in seen:
            continue

        seen.add(key)
        sources.append(
            Source(doc_id=meta["doc_id"], title=meta["title"], version=meta["version"])
        )

    return sources
