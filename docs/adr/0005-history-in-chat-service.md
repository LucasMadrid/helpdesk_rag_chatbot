# 0005. Chat history loaded and saved in ChatService, not RunnableWithMessageHistory

- **Status:** Accepted
- **Date:** 2026-11-09

## Context

W2-01 (ADR 0004) stores the messages of a session in `app-db` behind `BaseChatMessageHistory`. W2-02 has to use them: before the model call, the earlier turns of the request's `session_id` go into the prompt, and after it the new question and answer are saved. Then a follow-up such as "and what about Mac?" is understood.

Constraints:

- The routes are `async def`, and the history needs a connection borrowed asynchronously from the pool on `app.state.app_db_pool` (ADR 0003, ADR 0004).
- `ChatService` is built once at startup, so per-request things (the session, its connection) must come in per call, not in the constructor.
- The service should only know `BaseChatMessageHistory`, so unit tests need no database.

## Options considered

1. **`RunnableWithMessageHistory`** (`langchain_core.runnables.history`). It wraps the chain and loads and saves the history for you. In our installed `langchain-core` 1.7.4 it is deprecated since 1.3.3 and will be removed in 2.0 ("Use LangGraph's built-in persistence instead"). Its `get_session_history` factory is called synchronously inside the chain, with only values from `config["configurable"]`, so it has no clean way to borrow an async connection for the request.
2. **LangGraph persistence** (a checkpointer such as `langgraph-checkpoint-postgres`). It brings its own tables and its own state model, which would replace the `chat_history` table we just chose in ADR 0004, and it pushes us towards a graph we don't need yet.
3. **Load and save explicitly in `ChatService.reply`.** About five lines: `aget_messages()`, pass them to the chain, `aadd_messages()` after the answer.

## Decision

We choose option 3.

- `HELPDESK_PROMPT` has a `MessagesPlaceholder("history")` between the system message and the human `{question}`.
- `ChatService.reply` takes a keyword-only `history: BaseChatMessageHistory`. It loads with `await history.aget_messages()`, passes them as `history` to the chain, and only after `ainvoke` returns saves `HumanMessage(message)` and `AIMessage(answer)` in one `aadd_messages` call. There is no `try/except`: if the model call raises, the save line never runs and the error reaches the 503 handler.
- The route gets the history from a dependency: `get_db_connection` in `api/dependencies.py` borrows a connection with `async with pool.connection()` and `yield`s it (with `Depends(..., scope="function")`, so the connection goes back to the pool as soon as the route returns, before the response is sent), and `get_session_history` in `api/chat.py` builds the history with `get_chat_history(conn, body.session_id)`. It lives in `api/chat.py` because it needs `ChatRequest`, and `api/chat.py` already imports `api/dependencies.py` (a circular import otherwise).
- Route tests override `get_session_history` with an `InMemoryChatMessageHistory`, so FastAPI never calls `get_db_connection` and no pool is needed.

## Consequences

**Benefits**

- Every step is visible in our code and covered by unit tests: two replies give human/ai/human/ai, and a failed model call saves nothing.
- No deprecated wrapper and no new library or tables.
- The service still only knows `BaseChatMessageHistory`; Postgres stays in the adapter and the dependency.
- The history messages appear in the Langfuse trace input, which is where memory problems get debugged.

**Costs**

- **The connection is held for the whole route,** including the LLM call (up to 15 s plus retries). With the default pool (`min_size=4`, `max_size` = `min_size`), a fifth concurrent chat waits for a free connection, up to the pool's 30 s timeout. After that it gets `PoolTimeout`, which nothing handles yet, so the client gets a 500.
- **The two INSERTs are not one transaction.** `aadd_messages` runs one `executemany` and a commit, but the pool uses `autocommit=True`, so each row commits on its own. A crash between them could leave a question without its answer. Unlikely, and harmless for now.
- **Still no ownership.** Anyone who knows a `session_id` can read and extend that conversation. W2-03 adds the `sessions` table and the check.
- **Histories grow without limit,** so every turn costs more tokens. W2-04 trims them.

**When to revisit**

- `BaseChatMessageHistory` and `InMemoryChatMessageHistory` are themselves deprecated since `langchain-core` 1.6.4 (removal in 2.0). Before upgrading to 2.0, replace the port with our own small interface (`aget_messages` / `aadd_messages`) or with what LangChain recommends then; the adapter and this service are the only places to change.
- If load matters: borrow the connection twice (load, then save) instead of holding it during the LLM call, or raise `max_size`.

## Lessons learned

- A chat model is stateless. "Memory" is only the earlier messages we send again; the same follow-up in a new session got "what do you mean on Mac?" (experiment 1).
- `TestClient(app)` without `with` skips the lifespan, so `app.state` is empty. Overriding a dependency also skips its sub-dependencies, which is why the route tests don't need a pool.
- Saving only after the answer keeps the history made of complete turns. With the LLM unreachable, `/chat` returned 503 and the session stayed at 4 rows. The client resends the question, so a retry stores it once, with its answer.
- A pool connection is a scarce, shared resource, unlike a request ID, so we release it as early as we can. FastAPI's default `scope="request"` closes a `yield` dependency only after the response is sent; `scope="function"` closes it when the route returns.
- The scope saves only milliseconds. What limits concurrency is holding the connection during the LLM call. With `max_size=1`, two concurrent chats took 2.22 s and 3.89 s: the second one waited for the connection, not for the LLM. With the default pool, they took 2.24 s and 2.69 s.
