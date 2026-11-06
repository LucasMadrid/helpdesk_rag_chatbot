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
uv run pytest             # run the tests
```

The Langfuse UI opens at http://localhost:3000.

To stop the stack, run `docker compose down`. Don't add `-v` unless you want to
delete **all** data, including `app-db` (see [ADR 0001](docs/adr/0001-separate-app-database.md)).

### Start the API

```bash
uv run uvicorn helpdesk_rag_chatbot.main:create_app --factory --reload
```

Open http://127.0.0.1:8000/docs to try the endpoints:

- `GET /health` returns `{"status": "ok"}`.
- `POST /chat` takes `user_id` and `session_id` (both UUID7) and a `message`
  (1 to 1000 characters), and returns an `answer` and a `request_id`. To get a
  UUID7, run `uv run python -c "import uuid; print(uuid.uuid7())"`.

### See traces in Langfuse

Tracing is off by default. To send every `/chat` call to Langfuse, set
`LANGFUSE_ENABLED=true` in `.env`, along with the Langfuse keys from the UI
(Settings > API keys), then restart the API. Each call shows up as one trace
named `chat`, grouped by user and session, with the `request_id` in its metadata.
Tests and CI leave tracing off, so they never need Langfuse running.

### Check the LLM gateway

`uv run pytest` never calls a real LLM. To check that your `.env` reaches the
LiteLLM gateway, send one test message:

```bash
uv run python scripts/ping_llm.py
```

It prints the gateway, model, latency, reply and token usage, then `OK`. It
prints `FAILED: ...` and exits with code 1 if the call fails. The app talks to
the gateway through `ChatOpenAI` (see [ADR 0002](docs/adr/0002-llm-client.md)).

For the branch flow and pre-commit setup, see [CONTRIBUTING.md](CONTRIBUTING.md).
