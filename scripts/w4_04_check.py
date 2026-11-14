# Save as ~/w4_04_check.py, then from the repo root: uv run python ~/w4_04_check.py
import time
from pathlib import Path

from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.vectorstores import InMemoryVectorStore
from pinecone import Pinecone

from helpdesk_rag_chatbot.adapters.embeddings import get_embeddings
from helpdesk_rag_chatbot.adapters.vectorstore import (
    ensure_index,
    get_vector_store,
    index_chunks,
)
from helpdesk_rag_chatbot.config import get_settings
from helpdesk_rag_chatbot.ingestion.loaders import load_corpus
from helpdesk_rag_chatbot.splitters.registry import chunk_documents

s = get_settings()
chunks = chunk_documents(
    load_corpus(Path("data/docs")), s.splitter, s.chunk_size, s.chunk_overlap
)
pc = Pinecone(api_key=s.pinecone_api_key.get_secret_value())
ensure_index(pc, s.pinecone_index, s.embedding_dimensions)  # blocks until ready
store = get_vector_store(s, get_embeddings(s), namespace=s.splitter)
index_chunks(store, chunks)
index_chunks(store, chunks)  # twice on purpose
time.sleep(15)  # Pinecone's counts catch up a few seconds after an upsert

index = pc.Index(s.pinecone_index)
count = index.describe_index_stats().namespaces[s.splitter].vector_count
print("chunks:", len(chunks), "| vectors in namespace:", count)

q = "How many vacation days do I get in year 3?"
print("real:", [d.metadata["parent_id"] for d in store.similarity_search(q, k=3)])

fake = InMemoryVectorStore(DeterministicFakeEmbedding(size=1536))
index_chunks(fake, chunks)
print("fake:", [d.metadata["parent_id"] for d in fake.similarity_search(q, k=3)])
