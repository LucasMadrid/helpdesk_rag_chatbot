# 0001. Separate database for application data

- **Status:** Accepted
- **Date:** 2026-11-04

## Context

The chatbot needs to store application data: users, chat sessions and message history.

Langfuse already runs its own Postgres in the same Docker Compose project. We had to decide whether to reuse that database or run a separate one.

## Options considered

1. **Share Langfuse's Postgres.** One less container, but our data lives in a database that Langfuse owns and migrates.
2. **Run a separate `app-db` Postgres service.** One more container, but each database has a single owner.

## Decision

We run a separate Postgres service, `app-db`, for application data.

The two databases serve different purposes:

- `app-db` holds **product data** (users, sessions, history).
- Langfuse's Postgres holds **operational data** (traces, observability).

They have different owners, different retention rules and different risks, so they should not share a lifecycle. Resetting or upgrading Langfuse must never touch user conversations.

## Consequences

**Benefits**

- Langfuse can be reset, upgraded or replaced (for example by LangSmith) without losing user data.
- The app reaches `app-db` only through `BaseChatMessageHistory`, so it can later move to a managed Postgres or SQLite.

**Costs**

- One more container to run.
- `app-db` uses port **5433**, because Langfuse's Postgres already uses 5432.

**Watch out**

- Both services are in one Compose project (through `include`), so `docker compose down -v` deletes **all** volumes, including `app_db_data`.
- To reset only Langfuse, stop the stack and remove just the `langfuse_*` volumes (check the names with `docker volume ls`).

## Lessons learned

- Sharing infrastructure between components with different purposes ties their lifecycles together. Keeping it simple can create hidden risks.
- Don't commit configuration you can't explain. If something is copied, write down why it is there.
