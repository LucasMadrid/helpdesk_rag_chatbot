# 0006. Our own sessions table, claimed on the first chat

- **Status:** Proposed
- **Date:** 2026-11-11

## Context

Since W2-02, `/chat` loads and saves the messages of the request's `session_id` (ADR 0004, ADR 0005). Nothing checks who that session belongs to. Anyone who knows a `session_id` can read and extend that conversation. That is an IDOR (insecure direct object reference): knowing the ID is enough to get in.

W2-03 also needs `GET /sessions` (a user's session list, for the Streamlit UI) and `DELETE /sessions/{session_id}` (remove a conversation).

Constraints:

- The library's `chat_history` table (ADR 0004) has only `id`, `session_id`, `message` and `created_at`. It has no `user_id`, and we don't want to change a schema the library owns.
- The client already makes the UUIDv7 `session_id` and sends it with `user_id` on every `/chat` call.
- There is no login yet, so `user_id` is whatever the client sends.

## Options considered

1. **Add a `user_id` column to `chat_history`.** The library creates and queries that table, so we would be editing a schema we don't own. It would also repeat the owner on every message row and break when the library changes its DDL.
2. **Our own `sessions` table and an explicit `POST /sessions`.** The server makes the ID and the client must call it before chatting. That's an extra round trip and a breaking change for `/chat`, which already accepts client IDs.
3. **Our own `sessions` table, claimed on the first `/chat`.** The first message with a new `session_id` records its owner. After that, only the same user can use it.

For the claim itself:

- **SELECT, then INSERT if missing:** two first requests that arrive together can both see "missing" and both go on.
- **One `INSERT ... ON CONFLICT ... DO UPDATE ... WHERE ... RETURNING`:** Postgres settles the race inside one statement.

## Decision

We choose option 3, with the single-statement claim.

- `adapters/sessions.py` creates `sessions (session_id uuid PRIMARY KEY, user_id uuid NOT NULL, title text NOT NULL, created_at, updated_at)` and an index on `(user_id, updated_at DESC)` at startup, next to `chat_history`. There's no foreign key to `chat_history`, because that table belongs to the library.
- `PostgresSessionStore(conn)` has three methods over the request's pooled connection:
  - `open_history(session_id, user_id, title)` runs
    `INSERT ... ON CONFLICT (session_id) DO UPDATE SET updated_at = now() WHERE sessions.user_id = EXCLUDED.user_id RETURNING session_id`.
    A new ID gets inserted, the same owner gets `updated_at` bumped, and another owner gets no row back, which raises `SessionNotFound`. Only after that does it return the `BaseChatMessageHistory`. The title is the first 80 characters of the first message and never changes after that.
  - `list_sessions(user_id)` returns at most 50 `SessionSummary` rows, newest first, built with psycopg's `class_row`.
  - `delete_session(session_id, user_id)` deletes the `sessions` row and its `chat_history` rows inside one `conn.transaction()`. It uses our own `DELETE` (table name via `sql.Identifier`), not the library's `aclear()`, because `aclear()` calls `commit()`, and psycopg forbids that inside a transaction block.
- **404, not 403.** `SessionNotFound` covers both "doesn't exist" and "belongs to someone else", and one handler in `api/errors.py` turns it into a 404 with the request ID. A caller can't use the status code to probe which IDs exist (OWASP IDOR).
- `get_session_store` in `api/dependencies.py` replaces `get_session_history`. The route reads `ChatRequest` once and calls `open_history`. That also fixes the duplicated 422s: the body was validated twice, once in the route and once in the old dependency, so 3 bad fields gave 6 errors.
- While touching the error handlers, `psycopg_pool.PoolTimeout` now becomes a 503 with the request ID, instead of an unhandled 500 (a W2-02 follow-up).

## Consequences

**Benefits**

- One user can't read, extend, list or delete another user's session, and the rule is enforced in SQL in one place.
- `/chat` keeps its request shape: no new call before chatting.
- The library's table stays untouched, so upgrading `langchain-postgres` doesn't fight our schema.
- Deletes are all-or-nothing: no orphan messages without a session, and no session without its messages.

**Costs**

- **`user_id` is not authentication.** Anyone can still send someone else's `user_id`. This ADR makes the ownership check exist. When real login arrives, `user_id` comes from the token instead of the body or query, and that is the only thing that changes.
- **A session row is written before the LLM call.** If the model fails (503), the session exists with no messages and still shows in the list. That's acceptable: the user did start it.
- **Two tables without a foreign key.** Only `delete_session` keeps them in step. Deleting rows by hand in `psql` can leave orphans.
- **The claim runs on every `/chat`,** one extra statement per turn (an indexed primary-key upsert).
- **`LIMIT 50` with no pagination.** Enough for a helpdesk UI. Revisit if a user ever needs more.

**When to revisit**

- When login arrives: take `user_id` from the token and drop it from the body and query.
- If session rename, soft delete or pagination are needed.
- If `chat_history` ever moves to our own schema: add the foreign key with `ON DELETE CASCADE` and drop the manual delete.

## Lessons learned

- `ON CONFLICT ... DO UPDATE ... WHERE` returns no row when the `WHERE` is false. "No row back" is the ownership check, and it is race-free.
- A library method that commits on its own (`aclear()`) can't join our transaction. Inside `conn.transaction()` psycopg raises `ProgrammingError: Explicit commit() forbidden within a Transaction context`.
- Declaring the same Pydantic body in a route and in one of its dependencies makes FastAPI validate it twice, and every 422 error is listed twice.
