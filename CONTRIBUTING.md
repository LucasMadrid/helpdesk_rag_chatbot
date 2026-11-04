# Contributing

## Branch flow

```
main  <-  dev  <-  feature/*
```

- **`main`**: always working, demo-ready. Only updated from `dev` at the end of a stage, tagged `v0.1` (Stage 1: chatbot) and `v0.2` (Stage 2: RAG).
- **`dev`**: integration branch and the default target for pull requests.
- **`feature/<short-name>`**: one branch per piece of work, created from `dev`, for example `feature/week-1-foundations`.

## First-time setup

After cloning, run once:

```
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

Git hooks are not cloned with the repository, so without this step no checks run locally.
The `pre-commit` hook runs ruff (lint and format) and basic file checks; the `pre-push` hook runs `pytest`.

## Workflow

1. `git checkout dev && git pull`
2. `git checkout -b feature/<short-name>`
3. Commit small steps with clear messages.
4. Push and open a pull request into `dev`, filling in the template.
5. CI must pass and the review must be addressed before merging.
6. Merge with **squash merge**, then delete the feature branch.

## Releasing a stage

1. Open a pull request from `dev` into `main`.
2. After merging, tag the release: `git tag v0.1 && git push origin v0.1`.

## Code rules

- Python 3.14, dependencies managed with `uv`.
- The HTTP layer (`src/helpdesk_rag_chatbot/api`) only validates input and calls services.
- Vendors (LLM, vector store, history, tracing) are only imported in `src/helpdesk_rag_chatbot/adapters`.
- Secrets live in `.env` (never committed); document every setting in `.env.example`.
- Tests must run without network access or API keys.
