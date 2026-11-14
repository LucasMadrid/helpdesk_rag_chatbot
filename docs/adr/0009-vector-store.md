# 0009. Vector store: Pinecone through LangChain's VectorStore, one namespace per splitter

- **Status:** Accepted
- **Date:** 2026-11-14

## Context

W4-04 turns the chunks from W4-03 into vectors and stores them so later tickets can search by meaning. The project compares text splitters (Epic 7), so the same corpus will be indexed several times, once per splitter, and every index must be rebuilt from scratch whenever a document or a setting changes.

We had three questions to answer:

- **Which store, and how tightly do we bind to it?** The project decision (2026-11-03) is Pinecone free tier, kept swappable, with pgvector as the fallback.
- **How do the splitters stay apart?** Each splitter produces different chunks of the same documents, and their search results must never mix.
- **How do re-runs avoid duplicates?** Indexing the same corpus twice must leave the same number of vectors.

Constraints:

- The project runs on Python 3.14.
- Free Starter plan: 5 serverless indexes, 100 namespaces per index, 2 GB of storage, AWS `us-east-1` only. Record IDs are ASCII, at most 512 characters.
- Embeddings go through the academy's LiteLLM gateway, like the chat model (ADR 0002).
- Tests run without network or accounts.

## Options considered

The client:

1. **`langchain-pinecone` (`PineconeVectorStore`).** The official integration, a LangChain `VectorStore`. Its package metadata says Python `<3.14`, and it pins the `pinecone` SDK below 8 (we get 7.3.0, while the SDK itself is at 10.x).
2. **Our own adapter on the `pinecone` SDK 10.x**, implementing `VectorStore` ourselves. Supports 3.14 officially, but it is more code to write and test, and we would own the bugs.
3. **pgvector in the existing Postgres.** No new account, but it moves away from the project decision and needs a vector extension in both Postgres containers and in CI.

How the splitters stay apart:

1. **One index per splitter.** Clear separation, but the free plan allows only 5 indexes, and W7 needs 4 splitters.
2. **One index, one namespace per splitter.** Namespaces are separate partitions of one index: a query only sees its own namespace, and a whole namespace can be deleted in one call.
3. **One index, a `splitter` metadata filter.** Every query must remember the filter, and a rebuild must delete by filter.

## Decision

Option 1 for the client, and one index with one namespace per splitter.

- `adapters/embeddings.py` builds `OpenAIEmbeddings` pointed at the gateway, with `check_embedding_ctx_length=False` so plain text is sent instead of tiktoken token IDs. Model and size come from `EMBEDDING_MODEL` (default `text-embedding-3-small`) and `EMBEDDING_DIMENSIONS` (default 1536).
- `adapters/vectorstore.py` is the only module that imports `pinecone` or `langchain_pinecone`. Everything else talks to LangChain's `VectorStore` interface, so tests use `InMemoryVectorStore` and a later swap to pgvector changes this one module.
- One index, `PINECONE_INDEX` (default `helpdesk-corpus`), created by `ensure_index` only when `has_index` says it is missing: cosine metric, `ServerlessSpec(cloud="aws", region="us-east-1")`.
- The namespace is the splitter's registry name (`recursive` today).
- Each vector ID is `"{parent_id}#{chunk_index}#{first 16 hex chars of sha256(page_content)}"`. The same chunk always gets the same ID, so a re-run overwrites instead of duplicating.
- `uv` installs `langchain-pinecone` on 3.14 because uv ignores upper bounds on `requires-python`. Checked: 0.2.13 with `pinecone` 7.3.0, full test suite green, real upsert and search work.

## Consequences

**Benefits**

- Re-running the indexing is safe: 150 chunks indexed twice leave 150 vectors.
- A splitter comparison needs no new infrastructure: W7 adds namespaces, not indexes.
- W4-05 rebuilds one splitter by deleting its namespace and indexing again, without touching the others.
- The IDs are readable. A vector's ID shows its document, version and position, and all vectors of one document share a prefix.
- No test needs Pinecone, LiteLLM or a network.

**Costs**

- **We run a package outside its declared Python range.** A future `langchain-pinecone` or Python release could break it, and nobody upstream promises it works on 3.14.
- **We are pinned to `pinecone` 7.x**, three major versions behind, until `langchain-pinecone` is updated.
- **The text is stored twice:** `PineconeVectorStore` keeps `page_content` in the metadata under `text`, which counts towards the 40 KB metadata limit per record (an 800-character chunk is far below it).
- **The index dimension is fixed at creation.** Switching to an embedding model with a different size means deleting and recreating the index.
- **A changed chunk leaves its old vector behind** until the namespace is rebuilt, because the new text gets a new ID.

**When to revisit**

- If `langchain-pinecone` fails to install or import on a new Python or LangChain release: write our own adapter on the `pinecone` SDK 10.x (option 2), behind the same `VectorStore` interface.
- If `langchain-pinecone` releases a version that supports Python 3.14 and a newer SDK: upgrade and remove the caveat.
- If the free-plan limits get in the way, or the academy prefers fewer external accounts: move to pgvector (option 3).

## Lessons learned

- The self-check proved the ID scheme: indexing twice gave `chunks: 150 | vectors in namespace: 150`.
- Embeddings are what make the search work. For "How many vacation days do I get in year 3?", the real embeddings returned `hr-leave-policy@1.0` three times. `DeterministicFakeEmbedding` returned the VPN guide, the overtime policy and the known-errors FAQ: the vectors were made from a hash of the text, not its meaning. Fake embeddings are fine for testing the plumbing, not the results.
- The first chunk's ID in the Pinecone console was exactly the one computed on another machine (`gen-service-desk-contacts@1.0#0#231653dc07f44553`), so the hash is stable across machines and runs.
- Pinecone's counts are eventually consistent: `describe_index_stats` right after an upsert can show fewer vectors than were written, so the check waits a few seconds first.
- The console offers to "convert to a documents index". We don't: `langchain-pinecone` uses a classic vector index.
