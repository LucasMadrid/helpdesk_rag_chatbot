## What this PR does

<!-- One or two sentences. Link the milestone/week from the build guide. -->

## How to test it

<!-- Commands to run and what you should see. -->

## Self-check

<!-- Answer the week's self-check questions from the build guide here. -->

## Checklist

- [ ] Branch is `feature/*` and targets `dev`
- [ ] Tests pass locally from a clean environment (`uv sync && uv run pytest`)
- [ ] No secrets committed; every new setting is documented in `.env.example`
- [ ] Routes contain no business logic (HTTP layer only validates and calls services)
- [ ] README updated if setup or run steps changed
