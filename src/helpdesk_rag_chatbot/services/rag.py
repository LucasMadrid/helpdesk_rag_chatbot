from dataclasses import dataclass

from langchain.messages import SystemMessage
from langchain_core.documents import Document
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

    Each block is a header line ``[n] <title> <doc_id> v<version>`` followed
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
        header = f"[{index}] {meta['title']} {meta['doc_id']} v{meta['version']}"

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
