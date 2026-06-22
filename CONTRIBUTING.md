# Contributing

OpenAlpha is currently a local-first MVP. Contributions should describe the code as it exists today and mark planned behavior explicitly when the implementation is not complete yet.

## Local Setup

Backend:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install -e .
```

Frontend:

```powershell
cd frontend
npm.cmd install
cd ..
```

Run everything:

```powershell
openalpha run .
```

## Test Commands

Backend tests:

```powershell
.\.venv\Scripts\pytest.exe
```

Frontend build sanity check:

```powershell
cd frontend
npm.cmd run build
```

Frontend lint:

```powershell
cd frontend
npm.cmd run lint
```

## Repo Conventions Visible In Code

- backend code lives under `backend/app/`
- backend tests live under `backend/tests/`
- frontend code lives under `frontend/src/`
- persistence uses SQLite through SQLModel
- schemas are centralized in `backend/app/orchestrator/schemas.py`
- route composition is done in `backend/app/router.py`
- the active analysis graph is defined in `backend/app/orchestrator/base.py`

Current documentation rule:

- describe shipped behavior first
- if something is only planned, schema-only, or UI-only, say that directly

## Adding Docs

When adding or updating docs:

- prefer current implementation truth over aspirational design notes
- cross-link related docs from `README.md` where useful
- keep API names, route paths, and command examples aligned with the code
- include disclaimers where user-facing research output is discussed

## Adding An Agent

Use:

- [docs/adding-a-new-agent.md](/C:/Users/ernos/OpenAlpha/docs/adding-a-new-agent.md)

Expected work:

- add the agent implementation
- define or reuse a schema
- wire it into `AnalysisRunner`
- update context sync if a new runtime field is introduced
- add tests
- update docs

## Adding A Provider

Use:

- [docs/adding-a-new-provider.md](/C:/Users/ernos/OpenAlpha/docs/adding-a-new-provider.md)

Expected work:

- implement the provider against the appropriate base interface
- register or discover it in the current factory/service path
- preserve warning/fallback behavior
- avoid exposing provider-native shapes in agent outputs
- add tests and docs

## Testing Expectations

At minimum, new behavior should come with targeted tests for:

- happy path
- partial/fallback path
- failure path

If you change persistence, routes, or orchestrator stage behavior, add or update integration-style tests too.

## Current-State Accuracy

This matters for OpenAlpha specifically:

- the UI exposes `OpenAI` and `Ollama`
- the active agent runtime currently supports `OpenAI` only
- `fundamental_agent` and `critic_agent` exist in schemas but are not active runtime agents

If your contribution changes that reality, update the docs in the same change.
