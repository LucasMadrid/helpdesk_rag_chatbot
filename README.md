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

For the branch flow and pre-commit setup, see [CONTRIBUTING.md](CONTRIBUTING.md).
