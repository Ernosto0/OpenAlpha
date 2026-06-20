"""Compatibility entry point for local FastAPI runs.

The application lives in ``backend.app.main`` to match the project layout.
Keeping this module lets developers run ``uvicorn main:app --reload`` from the
repository root while imports stay aligned with the backend package.
"""

from backend.app.main import app

__all__ = ["app"]
