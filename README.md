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
  An optional `image` (`{"media_type": "image/png", "data": "<base64>"}`) adds a
  screenshot: PNG, JPEG or WebP, raw base64 without a `data:` prefix, at most
  5 MB, otherwise `422`. The image goes to the model with the question but is
  not stored; history keeps the text plus an `[image: <type>]` marker (see
  [ADR 0008](docs/adr/0008-images-not-stored.md)).
- `GET /sessions?user_id=<uuid7>` lists that user's sessions (`session_id`,
  `title`, `created_at`, `updated_at`), most recently used first, at most 50.
  A user with no sessions gets `[]`.
- `GET /sessions/{session_id}/messages?user_id=<uuid7>` returns that session's
  messages, oldest first, as `[{"role": "user" | "assistant", "content": ...}]`.
  A session that doesn't exist or belongs to another user gives `404`.
- `DELETE /sessions/{session_id}?user_id=<uuid7>` deletes the session and all
  its messages, and returns `204`.

### Chat UI

A Streamlit chat window: chat with an optional screenshot, list, reopen and
delete chats, and switch between two demo users. Install the `ui` extra once,
then run it from the repo root (so Streamlit finds `.streamlit/config.toml`):

```bash
uv sync --extra ui
uv run streamlit run src/helpdesk_rag_chatbot/ui/app.py
```

It opens at http://localhost:8501. For now it runs on demo data kept in memory
(`DemoBackend`), so it doesn't need the API; a grey "Demo data" badge says so.
Type "simulate error" to see how errors look. The page only talks to a
`ChatBackend` (`ui/backend.py`), never to the API code directly.

Change the look and wording without touching code:

| To change | Edit |
|---|---|
| Colours, corner radius, fonts, light and dark mode | `.streamlit/config.toml` |
| Name, tagline, placeholder, starter questions, demo users | `ui.toml` |

The demo users are not a login: like the API, the UI trusts the `user_id` it
sends.

### Sessions and ownership

There is no endpoint to create a session. The client makes a new UUID7, and the
first `POST /chat` with it claims the session for that `user_id`; the first 80
characters of the message become its title. After that, only the same user can
chat in, list or delete it. Another user gets `404` with
`{"detail": "Session not found.", "request_id": ...}`, the same answer as for a
session that doesn't exist, so session IDs can't be probed. See
[ADR 0006](docs/adr/0006-session-ownership.md).

`user_id` is not authentication yet: the API trusts whatever the client sends.

### Long chats and the history budget

Every message of a session stays in `app-db`, but `POST /chat` doesn't send all
of them to the model. Before each call it keeps only the newest earlier turns that
fit in `HISTORY_MAX_TOKENS` (default `2000`) and leaves out the oldest ones. The
system prompt and the new question are always sent and don't count against the
budget. Tokens are estimated at about 4 characters each, so the budget is
approximate.

A smaller budget makes each call cheaper and faster, but the model forgets earlier
turns sooner. `0` or a negative value stops the app at startup. Each Langfuse
trace shows `history_messages_total` and `history_messages_sent` in its metadata,
so you can see how much was left out.

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
- CI runs these tests against a `postgres:17` service container (see
  `.github/workflows/ci.yml`), and `tests/conftest.py` stops the run with exit
  code 4 if `TEST_APP_DB_URL` is missing there, so CI can't pass with them
  skipped. To run only the unit tests locally, use `uv run pytest -m "not integration"`.
- On Windows, psycopg's async mode doesn't work with the default Proactor event
  loop. The roundtrip script below switches to a `SelectorEventLoop`, but the
  integration tests don't yet, so run them on macOS, Linux or WSL.

To check the chat history by hand, run `uv run python scripts/chat_history_roundtrip.py`.
It uses `APP_DB_URL` from `.env`, saves two messages for a new session, reads them
back, prints them, then prints `OK`. Pass a session ID as the first argument to
reuse a session. Unlike the tests, it leaves its rows in the table so you can
look at them with `psql`.

For the branch flow and pre-commit setup, see [CONTRIBUTING.md](CONTRIBUTING.md).
