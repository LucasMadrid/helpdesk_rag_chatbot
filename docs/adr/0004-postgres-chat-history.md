# 0004. Chat history in Postgres through langchain-postgres, async, one pool

- **Status:** Accepted
- **Date:** 2026-11-09

## Context

Every `/chat` call starts from zero today, so a follow-up such as "and what about Mac?" can't work. W2-01 adds storage for the messages of a conversation, keyed by `session_id`, in the app's own Postgres (`app-db`, ADR 0001). W2-02 will read this history inside the chain, W2-03 adds a sessions API with ownership, and W2-04 trims long histories.

Constraints:

- The routes are `async def`. Anything that blocks inside them blocks every request in the process.
- ADR 0003 says shared clients are built once in the lifespan, stored on `app.state` and closed on shutdown. A database pool is exactly that kind of client.
- The chain should only depend on LangChain's `BaseChatMessageHistory`, so the storage can be swapped later (for example to Redis or an in-memory fake in tests).

## Options considered

**Where the messages live and in what shape**

1. **Our own table and SQL** (`messages(id, session_id, role, content, created_at, ...)`). We control the schema, but we'd have to write the serialization ourselves and keep it in sync with LangChain's message classes.
2. **`PostgresChatMessageHistory` from `langchain-postgres`**, which brings its own `chat_history` table (`id`, `session_id UUID`, `message JSONB`, `created_at`) and implements `BaseChatMessageHistory`. Messages are stored as LangChain's own JSON (`{"type": "human" | "ai", "data": {...}}`), so every message class round-trips, including tool calls and usage metadata.
3. **A different store** (Redis, a file). This would mean a new service to run and nothing gained at this stage.

**Sync or async driver**

1. A sync `psycopg.Connection` and the sync methods (`add_messages`, `messages`).
2. A **`psycopg.AsyncConnection`** and the async methods (`aadd_messages`, `aget_messages`).

**How connections are managed**

1. A new connection per request. That costs a TCP handshake plus Postgres authentication on every call, with no upper bound on connections.
2. **One `AsyncConnectionPool` per app process**, built in the lifespan (ADR 0003).

## Decision

- **We use the library's table.** `adapters/chat_history.py` exposes `get_chat_history(conn, session_id: UUID) -> BaseChatMessageHistory` and `create_chat_history_table(conn)`. The rest of the app only sees the base class. The adapter takes a `UUID` and converts it to `str` itself, because the library validates the string and raises `ValueError` for anything that isn't a UUID.
- **Async only.** We pass `async_connection=` and call the `a*` methods. A sync call inside an `async def` route would block the event loop for every user.
- **One pool, created in the lifespan.** `adapters/db.py` builds an unopened `AsyncConnectionPool` with `autocommit=True`. The lifespan opens it with `wait=True, timeout=5`, creates the table (`CREATE TABLE IF NOT EXISTS`, safe on every start), stores it on `app.state.app_db_pool`, and always closes it on shutdown, even if the Langfuse flush raises (nested `finally`).
- **Default pool sizes.** `min_size=4`, and `max_size` follows `min_size`. This is a training app with no load data, so there's nothing to justify other numbers yet.
- **Fail fast.** If `app-db` is unreachable, startup stops with `PoolTimeout` after 5 s. The alternative was to start without memory: `/health` would say OK, and every `/chat` would fail later with a 500 after the 10 s borrow timeout, or, from W2-02 on, answer without history.
- **No migration tool yet (YAGNI).** The library's `CREATE ... IF NOT EXISTS` is enough until we own tables with changing schemas (W2-03).
- **`langchain-postgres>=0.0.19`.** Versions up to 0.0.17 have a SQL injection in the vector store's inline-embedding path (GHSA-39qm-gv6q-f43r). We don't use the vector store, but the minimum keeps us off vulnerable versions.

## Consequences

**Benefits**

- Every LangChain message type is stored and rebuilt without code of our own.
- The chain and the unit tests only know `BaseChatMessageHistory`. Unit tests need no database, and the lifespan tests use a `FakePool`.
- Connections are reused, and their number is bounded by the pool.
- A missing database is visible at startup, not on the first user request.

**Costs**

- **The table has no owner.** Anyone who knows a `session_id` can read that conversation. W2-03 adds a `sessions` table with `user_id` and checks ownership before building a history.
- The schema belongs to the library. A future version could change it, and we have no migrations. Pin and read the changelog before upgrading.
- `PostgresChatMessageHistory.__init__` takes `table_name` and `session_id` as positional-only (`/`). Passing them by keyword raises `TypeError`, and our unit tests caught this once.
- The pool needs `autocommit=True`. The library commits after writes but not after reads, so without autocommit a read would leave the borrowed connection inside an open transaction.
- On Windows, psycopg's async mode can't use the default Proactor event loop. Scripts and tests have to use `SelectorEventLoop`.

**When to revisit**

- With more uvicorn workers, each process opens its own pool (4 connections each by default). Count them against Postgres's `max_connections` (100 by default).
- If we need fields the library's table doesn't have (per-message user, feedback, soft delete), we either add our own table next to it or move to option 1.

## Lessons learned

- `open()` on a psycopg pool doesn't check anything by default (`wait=False`). Without `wait=True`, the first failure shows up at the first borrowed connection, with a misleading "couldn't get a connection" error.
- An adapter is the place to absorb a library's quirks: string-only UUIDs, positional-only arguments, required autocommit. Callers then stay simple.
