# Contributing

## Branch flow

```
main  <-  dev  <-  feature/*
```

- **`main`**: always working, demo-ready. Only updated from `dev` at the end of a stage, tagged `v0.1` (Stage 1: chatbot) and `v0.2` (Stage 2: RAG).
- **`dev`**: integration branch and the default target for pull requests.
- **`feature/<short-name>`**: one branch per piece of work, created from `dev`, for example `feature/week-1-foundations`.

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
- The HTTP layer (`app/api`) only validates input and calls services.
- Vendors (LLM, vector store, history, tracing) are only imported in `app/adapters`.
- Secrets live in `.env` (never committed); document every setting in `.env.example`.
- Tests must run without network access or API keys.
