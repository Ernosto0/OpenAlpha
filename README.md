# OpenAlpha

Local-first, open-source AI equity research app.

## Backend Setup

Install Python 3.11 or newer, then create and activate a local virtual
environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install -e .
```

## Run The App

Start the local backend and frontend together from the repository root:

```powershell
openalpha run .
```

The command prints the local app URLs and starts both services:

```txt
Frontend:    http://127.0.0.1:5173
Backend API: http://127.0.0.1:8000
Health:      http://127.0.0.1:8000/api/health
```

OpenAlpha is an equity research tool, not a financial advisor. Generated
reports are for research and educational purposes only.

## Frontend Development

The React frontend lives in `frontend/` and uses Vite, TypeScript, Tailwind,
React Router, and a small local component library.

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open the app at:

```txt
http://127.0.0.1:5173
```

Set `VITE_API_BASE_URL` in `frontend/.env` if the backend is not running at
`http://127.0.0.1:8000`.
