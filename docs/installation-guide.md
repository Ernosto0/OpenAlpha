# Installation Guide

This guide covers the current local development setup for OpenAlpha as it exists in the repo today.

## Prerequisites

- Python `3.10+`
- Node.js with `npm`
- A working local Python installation that can create virtual environments

Backend packaging is defined in `pyproject.toml`. The frontend lives in `frontend/` and uses Vite.

## Python Setup

From the repository root:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install -e .
```

Notes:

- `pip install -e .` installs the `openalpha` CLI entrypoint.
- `requirements-dev.txt` adds test and lint dependencies used by the backend workflow.

## Frontend Setup

From the repository root:

```powershell
cd frontend
npm.cmd install
cd ..
```

## Run Both Services With The CLI

The main combined entrypoint is:

```powershell
openalpha run .
```

What it does:

- validates the repo structure
- prepares `DATABASE_URL` if needed
- initializes SQLite
- starts FastAPI with Uvicorn from the repo root
- starts the Vite frontend from `frontend/`

Default ports:

- frontend: `5173`
- backend: `8000`

If a preferred port is taken, the CLI searches forward for an available port.

## Run Backend And Frontend Manually

Backend from the repo root:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend from `frontend/`:

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

If needed, set the frontend API base URL:

```powershell
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
```

## Local Settings And API Keys

OpenAlpha stores app settings in the local SQLite database table `settings`.

Typical first-run flow:

1. Start the app.
2. Open `Settings`.
3. Add an OpenAI API key.
4. Click `Apply Settings`.
5. Click `Test OpenAI`.
6. Return to `Analysis` and run a report.

Current behavior:

- OpenAI is the only implemented LLM runtime for the active agents.
- Ollama settings are stored and shown in the UI, but live Ollama testing is not implemented and the agent factories still reject non-OpenAI provider names.

## Troubleshooting

### `openalpha` Command Not Found

Re-activate your virtualenv and reinstall the package:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### `npm` Not Found

Install Node.js, then rerun:

```powershell
cd frontend
npm.cmd install
```

### The Virtualenv Points At A Removed Python Install

This repo already demonstrates a common Windows failure mode: a virtualenv can keep launchers that point to a Python path that no longer exists.

Symptoms:

- `python` inside `.venv` fails even though `.venv\Scripts\python.exe` exists
- the launcher reports a missing base interpreter path

Fix by recreating the environment:

```powershell
Remove-Item -Recurse -Force .venv
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install -e .
```

If you do not want to delete immediately, inspect `.\.venv\pyvenv.cfg` first to confirm it references an old Python installation.

### OpenAI Provider Test Fails

Check:

- the API key is present in `Settings`
- outbound network access to `https://api.openai.com`
- the selected model is a real OpenAI model your account can access

### Ollama Looks Configured But Analysis Still Fails

That is expected in the current codebase. The settings UI supports local runtime fields, but the runtime agent provider factories currently support `OpenAI` only.

## Next Docs

- [README.md](/C:/Users/ernos/OpenAlpha/README.md)
- [docs/architecture.md](/C:/Users/ernos/OpenAlpha/docs/architecture.md)
- [docs/providers.md](/C:/Users/ernos/OpenAlpha/docs/providers.md)
