from hashlib import sha256

from langchain.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from helpdesk_rag_chatbot.config import Settings


def chunk_id(chunk: Document) -> str:
    """
    Build a stable vector ID for one chunk.

    The format is ``{parent_id}#{chunk_index}#{hash}``, where ``hash`` is the
    first 16 hex characters of the SHA-256 of ``page_content`` (UTF-8). The same
    chunk always gets the same ID, so re-ingesting overwrites its vector instead
    of adding a duplicate, and a changed chunk text gets a new ID.

    :param chunk: A chunk from the splitter, with ``parent_id`` and
        ``chunk_index`` in its metadata.
    :return: The vector ID, e.g. ``"vpn-setup@2#3#9f86d081884c7d65"``.
    :raises KeyError: If ``parent_id`` or ``chunk_index`` is missing from the
        metadata.
    """
    digest = sha256(chunk.page_content.encode("utf-8")).hexdigest()[:16]
    return f"{chunk.metadata['parent_id']}#{chunk.metadata['chunk_index']}#{digest}"


def index_chunks(store: VectorStore, chunks: list[Document]) -> list[str]:
    """
    Embed and save chunks in the vector store, one vector per chunk.

    Each chunk is stored under its ``chunk_id``. Saving is an upsert, so indexing
    the same chunks again overwrites their vectors instead of adding duplicates.
    The store embeds the text itself, using the ``Embeddings`` it was built with.
    An empty list returns ``[]`` without calling the store.

    For Pinecone, metadata values must be strings, numbers, booleans or lists of
    strings; ``None``, nested dicts or dates are rejected.

    :param store: Any LangChain vector store, e.g. ``PineconeVectorStore`` in
        production or ``InMemoryVectorStore`` in tests.
    :param chunks: Chunks from the splitter, with ``parent_id`` and
        ``chunk_index`` in their metadata.
    :return: The IDs the store wrote, in the same order as ``chunks``.
    :raises KeyError: If a chunk is missing ``parent_id`` or ``chunk_index``.
    """
    if not chunks:
        return []

    return store.add_documents(chunks, ids=[chunk_id(c) for c in chunks])


def get_vector_store(
    settings: Settings, embeddings: Embeddings, namespace: str
) -> VectorStore:
    """
    Build the Pinecone vector store for one namespace.

    The constructor makes a network call: it looks up the index host from
    Pinecone, so the index must already exist and Pinecone must be reachable.
    Build it once at startup and share it (see ADR 0003), not per request.

    The API key is passed as a plain string, because ``PineconeVectorStore``
    wraps it in its own ``SecretStr``; passing the ``SecretStr`` from settings
    would send the masked ``"**********"`` as the key.

    :param settings: Application settings; uses ``pinecone_index`` and
        ``pinecone_api_key``.
    :param embeddings: The embedding client (see ``get_embeddings``). Its vector
        size must match the index dimension.
    :param namespace: The Pinecone namespace to read and write. Vectors in other
        namespaces of the same index are not visible.
    :return: A ``VectorStore`` bound to ``pinecone_index`` and ``namespace``.
    :raises ValueError: If the API key or index name is empty.
    """
    return PineconeVectorStore(
        index_name=settings.pinecone_index,
        namespace=namespace,
        embedding=embeddings,
        pinecone_api_key=settings.pinecone_api_key.get_secret_value(),
    )


def ensure_index(client: Pinecone, name: str, dimension: int) -> None:
    """
    Create the Pinecone index if it does not exist, or check the one that does.

    Safe to call repeatedly. A new index is serverless on AWS ``us-east-1`` with
    cosine similarity, and the call blocks until Pinecone reports it ready (no
    timeout). An existing index is left as it is, but its dimension must equal
    ``dimension``: otherwise every upsert would be rejected later, so this fails
    at startup instead.

    :param client: A Pinecone SDK client (``pinecone.Pinecone``), not the
        LangChain vector store.
    :param name: The index name, usually ``settings.pinecone_index``.
    :param dimension: The vector size, which must equal
        ``settings.embedding_dimensions``.
    :raises ValueError: If the index exists with a different dimension.
    """
    if not client.has_index(name):
        client.create_index(
            name=name,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        return

    existing = client.describe_index(name).dimension
    if existing != dimension:
        raise ValueError(
            f"Pinecone index {name!r} has dimension {existing}, but the embedding "
            f"model produces {dimension}. Set EMBEDDING_DIMENSIONS to {existing} "
            "or use a new index."
        )
