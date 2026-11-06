# 0003. Shared clients are created once at startup

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

`POST /chat` gets its `ChatService` from the `get_chat_service` dependency. In W1-08 that provider builds a new `ChatOpenAI` and a new `ChatService` on every request. `get_settings` is cached, so every request reads the same config, but the same config does not give the same object: 100 requests create 100 models, 100 chains and 100 HTTP clients.

Each new `ChatOpenAI` opens its own HTTP client, so no connection to the LiteLLM proxy is reused. Every request pays a fresh TCP and TLS handshake, and the chain is rebuilt each time.

More long-lived clients are coming: the Pinecone index, the Postgres connection pool and the Langfuse callback handler. We need one rule for when these objects are created and who owns them.

## Options considered

1. **Build per request** in the dependency provider (what W1-08 does). This is simple and easy to test, but it wastes connections and repeats setup on every call.
2. **A classic Singleton**: a class that overrides `__new__`, or a module-level global such as `model = ChatOpenAI(...)`. The object is created when the module is first imported. Importing the module then needs a valid `.env`, even in tests that never call the LLM, and the object is hard to replace.
3. **Build once in the app's `lifespan`**, store it on `app.state`, and hand it out through `Depends`. `create_app()` and its lifespan are the only place that builds shared objects (the composition root).

## Decision

We use option 3. Each shared client is created once per app process in the `lifespan` function, stored on `app.state`, and returned by a dependency provider such as `get_chat_service(request)`. Routes keep asking for `ChatServiceDependency` and never know how the object was built.

We don't need a pool for `ChatOpenAI`. A pool is for resources that only one caller can use at a time, such as DB connections. `ChatOpenAI` is stateless, safe to share across concurrent requests, and keeps its own HTTP connection pool inside. One shared instance is enough.

## Consequences

**Benefits**

- HTTP connections to LiteLLM are reused across requests, and the chain is built once.
- Startup fails fast: a missing or invalid setting stops the app at boot instead of failing on the first `/chat` request.
- Tests are unchanged. `app.dependency_overrides[get_chat_service]` still swaps in a `FakeListChatModel`, so tests need no `.env` and no network.
- The same rule covers every later client (Pinecone, Postgres pool, Langfuse).

**Costs**

- Anything stored on `app.state` must be safe to share. It must not keep per-request or per-user state on the object. Per-request data, such as `session_id`, chat history or the request ID, is passed as an argument, never stored on the shared client.
- Clients that hold resources (the Postgres pool, Langfuse's flush) must be closed in the lifespan's shutdown part, after `yield`.

**Watch out**

- `@lru_cache` on `get_chat_service(settings)` is not a shortcut. `Settings` is a Pydantic model and isn't hashable, so the cache call fails.
- Changing config needs an app restart. That's fine for us, since settings come from `.env`.

**When to revisit**

- If we run several workers or processes, each one gets its own instance. That's expected, but it should be counted when sizing the Postgres pool.

## Lessons learned

- Same config ≠ same object. Caching the inputs (`Settings`) does not cache what you build from them.
- "Singleton" here means a lifetime choice (one per app, owned by the composition root), not a class pattern. A shared object has to be safe to share, not just the only one.
