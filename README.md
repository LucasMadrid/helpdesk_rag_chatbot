# helpdesk_rag_chatbot

A RAG chatbot oriented to Helpdesk about a fictional company

## Run it locally

You need [Docker](https://docs.docker.com/get-docker/) and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
cp .env.example .env      # then fill in real values
docker compose up -d      # starts app-db (port 5433) and the Langfuse stack
docker compose ps         # wait until every service is healthy
uv sync                   # creates .venv and installs dependencies from uv.lock
uv run ruff check .       # lint
uv run ruff format --check .  # formatting (CI runs both ruff checks)
uv run pytest             # run the tests
```

The Langfuse UI opens at http://localhost:3000.

To stop the stack, run `docker compose down`. Don't add `-v` unless you want to
delete **all** data, including `app-db` (see [ADR 0001](docs/adr/0001-separate-app-database.md)).

### Start the API

```bash
uv run uvicorn helpdesk_rag_chatbot.main:create_app --factory --reload
```

The API needs `app-db` running. At startup it opens a connection pool and creates
the `chat_history` and `sessions` tables if they're missing. If `app-db` can't be
reached, startup stops after about 5 seconds with `PoolTimeout` (see
[ADR 0004](docs/adr/0004-postgres-chat-history.md)).

Open http://127.0.0.1:8000/docs to try the endpoints:

- `GET /health` returns `{"status": "ok"}`.
- `POST /chat` takes `user_id` and `session_id` (both UUID7) and a `message`
  (1 to 1000 characters), and returns an `answer` and a `request_id`. To get a
  UUID7, run `uv run python -c "import uuid; print(uuid.uuid7())"`.
- `GET /sessions?user_id=<uuid7>` lists that user's sessions (`session_id`,
  `title`, `created_at`, `updated_at`), most recently used first, at most 50.
  A user with no sessions gets `[]`.
- `DELETE /sessions/{session_id}?user_id=<uuid7>` deletes the session and all
  its messages, and returns `204`.

### Sessions and ownership

There is no endpoint to create a session. The client makes a new UUID7, and the
first `POST /chat` with it claims the session for that `user_id`; the first 80
characters of the message become its title. After that, only the same user can
chat in, list or delete it. Another user gets `404` with
`{"detail": "Session not found.", "request_id": ...}`, the same answer as for a
session that doesn't exist, so session IDs can't be probed. See
[ADR 0006](docs/adr/0006-session-ownership.md).

`user_id` is not authentication yet: the API trusts whatever the client sends.

### See traces in Langfuse

Tracing is off by default. To send every `/chat` call to Langfuse, set
`LANGFUSE_ENABLED=true` in `.env`, along with the Langfuse keys from the UI
(Settings > API keys), then restart the API. Each call shows up as one trace
named `chat`, grouped by user and session, with the `request_id` in its metadata.
Tests and CI leave tracing off, so they never need Langfuse running.

### Logs and request IDs

The API writes one JSON object per log line to the terminal. Set the level with
`LOG_LEVEL` in `.env`: one of `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`,
in uppercase (default `INFO`). Any other value stops the app at startup.

Every request gets a `request_id` (UUID7). It is returned in the `X-Request-ID`
response header and in the response body, and it is added to every log line
written during that request and to the Langfuse trace. To follow one request,
search the logs for its ID.

If the LLM gateway can't be reached, times out or rate-limits the call, `POST /chat`
returns `503` with `{"detail": ..., "request_id": ...}`, so the client can retry
later. The same happens when every database connection stays busy for the pool's
wait time (`PoolTimeout`), because the service is overloaded rather than broken.
Any other unexpected error returns `500` in the same shape.

### Check the LLM gateway

`uv run pytest` never calls a real LLM. To check that your `.env` reaches the
LiteLLM gateway, send one test message:

```bash
uv run python scripts/ping_llm.py
```

It prints the gateway, model, latency, reply and token usage, then `OK`. It
prints `FAILED: ...` and exits with code 1 if the call fails. The app talks to
the gateway through `ChatOpenAI` (see [ADR 0002](docs/adr/0002-llm-client.md)).

### Integration tests (real Postgres)

`uv run pytest` needs no database. The tests marked `integration` talk to a real
`app-db` and are skipped unless `TEST_APP_DB_URL` is set:

```bash
docker compose up -d app-db
TEST_APP_DB_URL=postgresql://helpdesk:<password>@127.0.0.1:5433/helpdesk \
  uv run pytest -m integration
```

- Use the password from your `.env`. `TEST_APP_DB_URL` is read from the process
  environment, not from `.env`, so export it in the shell (some editors' terminals
  inject `.env` variables for you).
- Each test uses new UUID7 user and session IDs and deletes its own rows
  afterwards, so it's safe to run against your local `app-db`.
- CI has no Postgres yet, so these tests are skipped there. To run only the unit
  tests locally, use `uv run pytest -m "not integration"`.
- On Windows, psycopg's async mode doesn't work with the default Proactor event
  loop. The roundtrip script below switches to a `SelectorEventLoop`, but the
  integration tests don't yet, so run them on macOS, Linux or WSL.

To check the chat history by hand, run `uv run python scripts/chat_history_roundtrip.py`.
It uses `APP_DB_URL` from `.env`, saves two messages for a new session, reads them
back, prints them, then prints `OK`. Pass a session ID as the first argument to
reuse a session. Unlike the tests, it leaves its rows in the table so you can
look at them with `psql`.

For the branch flow and pre-commit setup, see [CONTRIBUTING.md](CONTRIBUTING.md).
