"""Ingestion pipeline: load the corpus, chunk it and index it in Pinecone."""

import argparse
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from langchain_core.vectorstores import VectorStore
from pinecone import Pinecone

from helpdesk_rag_chatbot.adapters.embeddings import get_embeddings
from helpdesk_rag_chatbot.adapters.vectorstore import (
    clear_namespace,
    ensure_index,
    get_vector_store,
    index_chunks,
)
from helpdesk_rag_chatbot.config import Settings, get_settings
from helpdesk_rag_chatbot.ingestion.loaders import load_corpus
from helpdesk_rag_chatbot.splitters.registry import SPLITTERS, chunk_documents
from helpdesk_rag_chatbot.utils.logging_setup import configure_logging

DOCS_DIR = Path("data/docs")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestReport:
    """
    Summary of one ingestion run.

    :param splitter: The splitter used, which is also the namespace written to.
    :param documents: The number of documents loaded from the corpus folder.
    :param chunks: The number of chunks the splitter produced.
    :param deleted: The number of vectors the namespace held before it was
        cleared.
    :param indexed: The number of vectors written to the namespace.
    """

    splitter: str
    documents: int
    chunks: int
    deleted: int
    indexed: int


def ingest(
    settings: Settings, client: Pinecone, store: VectorStore, docs_dir: Path = DOCS_DIR
) -> IngestReport:
    """
    Rebuild one namespace of the index from the documents on disk.

    Loads every supported document in ``docs_dir``, splits it with the
    configured splitter, deletes every vector in the splitter's namespace and
    then indexes the new chunks. The namespace is named after the splitter, so
    each splitter's vectors are kept apart and can be compared. Clearing first
    removes vectors for chunks that no longer exist, at the cost of the
    namespace being empty or partial until indexing finishes.

    :param settings: Application settings; uses ``splitter``, ``chunk_size``,
        ``chunk_overlap`` and ``pinecone_index``.
    :param client: A Pinecone SDK client, used to clear the namespace.
    :param store: The vector store to write to. It must be bound to the
        ``settings.splitter`` namespace (see ``get_vector_store``).
    :param docs_dir: The corpus folder; defaults to ``data/docs``.
    :return: An ``IngestReport`` with the counts for this run.
    """

    # Extract the documents
    documents = load_corpus(docs_dir)

    # Transform the documents into chunks
    chunks = chunk_documents(
        documents, settings.splitter, settings.chunk_size, settings.chunk_overlap
    )

    # Clean namespace
    vectors_deleted = clear_namespace(
        client, settings.pinecone_index, settings.splitter
    )

    # Load the document's chunk into the Vector Database
    indexed_ids = index_chunks(store, chunks)

    # Build final report
    ingest_report = IngestReport(
        splitter=settings.splitter,
        documents=len(documents),
        chunks=len(chunks),
        deleted=vectors_deleted,
        indexed=len(indexed_ids),
    )
    return ingest_report


def _int_at_least(minimum: int) -> Callable[[str], int]:
    """
    Build an argparse ``type`` that accepts integers of at least ``minimum``.

    Mirrors the ``gt=0`` / ``ge=0`` rules on the chunk settings, which
    ``model_copy`` would otherwise skip.

    :param minimum: The smallest accepted value.
    :return: A converter that returns the integer or raises
        ``argparse.ArgumentTypeError``.
    """

    def convert(value: str) -> int:
        number = int(value)
        if number < minimum:
            raise argparse.ArgumentTypeError(f"must be at least {minimum}")
        return number

    convert.__name__ = "int"  # argparse shows it: "invalid int value"
    return convert


def parse_args(argv: list[str] | None, settings: Settings) -> argparse.Namespace:
    """
    Parse the ingest command-line options, with defaults from settings.

    ``--splitter`` must be a key of ``SPLITTERS``, ``--chunk-size`` at least 1
    and ``--chunk-overlap`` at least 0 (the same rules as the settings, which
    ``model_copy`` would otherwise skip).

    :param argv: The arguments to parse, without the program name; ``None``
        reads ``sys.argv[1:]``.
    :param settings: Application settings; supply ``splitter``, ``chunk_size``
        and ``chunk_overlap`` when an option is not given.
    :return: The parsed options, with ``splitter``, ``chunk_size`` and
        ``chunk_overlap`` attributes, never ``None``.
    :raises SystemExit: If an option is unknown or invalid, e.g. a splitter not
        in ``SPLITTERS`` or a negative overlap. argparse prints the error first.
    """
    parser = argparse.ArgumentParser(
        description="Rebuild one splitter's namespace from data/docs."
    )
    parser.add_argument(
        "--splitter",
        default=settings.splitter,
        choices=sorted(SPLITTERS),
        help="Splitter and namespace to rebuild (default: %(default)s)",
    )
    parser.add_argument(
        "--chunk-size",
        type=_int_at_least(1),
        default=settings.chunk_size,
        help="Maximum chunk length in characters (default: %(default)s)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=_int_at_least(0),
        default=settings.chunk_overlap,
        help="Characters shared between neighbouring chunks (default: %(default)s)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """
    Run ingestion from the command line and log the report.

    Reads settings from the environment, applies any command-line overrides,
    makes sure the Pinecone index exists, then rebuilds the namespace of the
    chosen splitter. Needs the LiteLLM gateway (for embeddings) and Pinecone to
    be reachable. The counts are logged as one JSON line (``"ingest done"``
    with the ``IngestReport`` fields), like the API's logs.

    :param argv: The arguments to parse, without the program name; ``None``
        reads ``sys.argv[1:]``.
    :raises SystemExit: If an option is unknown or invalid.
    :raises ValueError: If the index exists with a different dimension.
    """
    settings = get_settings()
    configure_logging(level=settings.log_level)
    args = parse_args(argv, settings)

    settings = settings.model_copy(
        update={
            "splitter": args.splitter,
            "chunk_size": args.chunk_size,
            "chunk_overlap": args.chunk_overlap,
        }
    )

    client = Pinecone(api_key=settings.pinecone_api_key.get_secret_value())
    ensure_index(client, settings.pinecone_index, settings.embedding_dimensions)
    store = get_vector_store(settings, get_embeddings(settings), settings.splitter)

    report = ingest(settings, client, store)
    logger.info("ingest done", extra=asdict(report))


if __name__ == "__main__":
    main()
