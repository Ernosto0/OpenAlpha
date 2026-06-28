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
py -m openalpha setup .
```

Notes:

- `py -m openalpha setup .` creates `.venv` if needed, installs the local package there, and runs `npm install` in `frontend/`.
- Contributors who also want test and lint dependencies can run `py -m openalpha setup . --dev`.
- PowerShell activation is optional. If you want it, run `.\.venv\Scripts\Activate.ps1` after setup.

If `openalpha` is already installed in the active environment, you can also use `openalpha setup .`.

## Run Both Services With The CLI

The main combined entrypoint is:

```powershell
py -m openalpha run .
```

What it does:

- validates the repo structure
- reuses the project `.venv` automatically when available
- prepares `DATABASE_URL` if needed
- initializes SQLite
- starts FastAPI with Uvicorn from the repo root
- starts the Vite frontend from `frontend/`

If you activated `.venv` first, `openalpha run .` is equivalent.

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
3. Add an API key for OpenAI, Claude, or Gemini.
4. Click `Apply Settings`.
5. Click the matching provider test action.
6. Return to `Analysis` and run a report.

Current behavior:

- OpenAI, Claude, and Gemini are implemented LLM runtimes for the active agents.
- Each remote provider can be configured and credential-tested from `Settings`.
- Ollama settings are stored in the database and the backend now supports live connectivity tests, installed-model discovery, and active local-runtime analysis runs.

## Troubleshooting

### `openalpha` Command Not Found

Re-activate your virtualenv and reinstall the package:

```powershell
.\.venv\Scripts\Activate.ps1
py -m openalpha setup .
```

### `npm` Not Found

Install Node.js, then rerun:

```powershell
py -m openalpha setup .
```

### The Virtualenv Points At A Removed Python Install

This repo already demonstrates a common Windows failure mode: a virtualenv can keep launchers that point to a Python path that no longer exists.

Symptoms:

- `python` inside `.venv` fails even though `.venv\Scripts\python.exe` exists
- the launcher reports a missing base interpreter path

Fix by recreating the environment:

```powershell
Remove-Item -Recurse -Force .venv
py -m openalpha setup .
```

If you do not want to delete immediately, inspect `.\.venv\pyvenv.cfg` first to confirm it references an old Python installation.

### OpenAI Provider Test Fails

Check:

- the API key is present in `Settings`
- outbound network access to `https://api.openai.com`
- the selected model is a real OpenAI model your account can access

### Claude Or Gemini Provider Test Fails

Check:

- the API key is present in `Settings`
- outbound network access to the provider API
- the selected model is a real model your account can access

### Ollama Looks Configured But Analysis Still Fails

If Ollama fails to start a run, check that the configured base URL is reachable, the Ollama service is running, and the selected model is installed locally.

## Next Docs

- [README.md](../README.md)
- [docs/architecture.md](architecture.md)
- [docs/providers.md](providers.md)
