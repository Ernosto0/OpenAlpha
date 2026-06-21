from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType

from openalpha.cli import (
    _default_database_url,
    _display_database_url,
    _prepare_database,
    _print_startup_message,
)


def test_startup_message_positions_openalpha(capsys) -> None:
    _print_startup_message(
        frontend_url="http://127.0.0.1:5173",
        backend_url="http://127.0.0.1:8000",
    )

    output = capsys.readouterr().out

    assert "OpenAlpha is running on this host." in output
    assert "Frontend:    http://127.0.0.1:5173" in output
    assert "Backend API: http://127.0.0.1:8000" in output
    assert "AI stock reports you can audit." in output
    assert "local-first, open-source AI equity research app" in output
    assert "not personalized financial advice" in output


def test_default_database_url_points_to_project_root() -> None:
    project_root = Path("C:/example/OpenAlpha")

    assert (
        _default_database_url(project_root)
        == "sqlite:///C:/example/OpenAlpha/openalpha.db"
    )


def test_prepare_database_sets_default_url_and_initializes(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    initialized_with: list[str] = []
    session_module = ModuleType("backend.app.db.session")

    def init_db() -> None:
        initialized_with.append(os.environ["DATABASE_URL"])

    session_module.init_db = init_db
    monkeypatch.setitem(sys.modules, "backend.app.db.session", session_module)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    env = _prepare_database(project_root=tmp_path, env={})

    expected_database_url = _default_database_url(tmp_path)
    output = capsys.readouterr().out

    assert env["DATABASE_URL"] == expected_database_url
    assert initialized_with == [expected_database_url]
    assert "DATABASE_URL" not in os.environ
    assert "Setting up local database..." in output
    assert f"Database ready: {_display_database_url(expected_database_url)}" in output
