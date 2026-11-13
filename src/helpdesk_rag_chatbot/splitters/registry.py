from collections.abc import Callable

from langchain_core.documents import Document
from langchain_text_splitters import TextSplitter

from helpdesk_rag_chatbot.splitters.recursive import build_recursive_splitter

SPLITTERS: dict[str, Callable[[int, int], TextSplitter]] = {
    "recursive": build_recursive_splitter
}


def get_splitter(name: str, chunk_size: int, chunk_overlap: int) -> TextSplitter:
    """
    Look up a splitter factory by name in ``SPLITTERS`` and build it.

    :param name: Registry key of the splitter, e.g. ``recursive``.
    :param chunk_size: Maximum chunk length in characters.
    :param chunk_overlap: Number of characters shared between consecutive chunks.
    :return: The configured ``TextSplitter``.
    :raises ValueError: If ``name`` is not in ``SPLITTERS``.
    """
    if name not in SPLITTERS:
        raise ValueError(
            f"Unknown splitter {name!r}. Available: {', '.join(sorted(SPLITTERS))}"
        )

    return SPLITTERS[name](chunk_size, chunk_overlap)


def chunk_documents(
    documents: list[Document],
    splitter_name: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    """
    Split each document into chunks that point back to their parent.

    Each chunk keeps its parent's metadata plus ``start_index``, and gains
    ``parent_id``, ``chunk_index`` (0-based within the parent) and ``splitter``.

    :param documents: Parent documents, each with an ``id``.
    :param splitter_name: Registry key of the splitter, e.g. ``recursive``.
    :param chunk_size: Maximum chunk length in characters.
    :param chunk_overlap: Number of characters shared between consecutive chunks.
    :return: All chunks, grouped by parent in input order.
    :raises ValueError: If the splitter name is unknown.
    """
    splitter = get_splitter(splitter_name, chunk_size, chunk_overlap)

    chunks: list[Document] = []
    for doc in documents:
        for index, chunk in enumerate(splitter.split_documents([doc])):
            chunk.metadata["parent_id"] = doc.id
            chunk.metadata["chunk_index"] = index
            chunk.metadata["splitter"] = splitter_name
            chunks.append(chunk)

    return chunks
