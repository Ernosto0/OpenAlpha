from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from openalpha.cli import (
    _default_database_url,
    _display_database_url,
    _prepare_database,
    _print_startup_message,
    build_parser,
    run_app,
    setup_app,
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


def test_build_parser_accepts_setup_dev_flag() -> None:
    args = build_parser().parse_args(["setup", "repo", "--dev"])

    assert args.command == "setup"
    assert args.path == "repo"
    assert args.dev is True
    assert args.func is setup_app


def test_setup_app_installs_python_and_frontend_dependencies(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    (frontend_dir / "package.json").write_text("{}", encoding="utf-8")

    calls: list[tuple[list[str], Path]] = []
    venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"

    def fake_run(command: list[str], *, cwd: Path | None = None, check: bool, env=None) -> SimpleNamespace:
        calls.append((command, cwd))
        if command[:4] == ["py", "-3.10", "-m", "venv"]:
            venv_python.parent.mkdir(parents=True, exist_ok=True)
            venv_python.write_text("", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("openalpha.cli.subprocess.run", fake_run)
    monkeypatch.setattr(
        "openalpha.cli.shutil.which",
        lambda name: "C:/Program Files/nodejs/npm.cmd" if name in {"npm.cmd", "py"} else None,
    )

    result = setup_app(SimpleNamespace(path=str(tmp_path), dev=True))
    output = capsys.readouterr().out

    assert result == 0
    assert calls == [
        (["py", "-3.10", "-m", "venv", ".venv"], tmp_path),
        (
            [
                str(venv_python),
                "-c",
                "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)",
            ],
            None,
        ),
        ([str(venv_python), "-m", "ensurepip", "--upgrade"], tmp_path),
        (
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--upgrade",
                "pip",
                "setuptools>=68",
                "wheel",
            ],
            tmp_path,
        ),
        ([str(venv_python), "-m", "pip", "install", "-e", ".[dev]"], tmp_path),
        (["npm.cmd", "install"], frontend_dir),
    ]
    assert "OpenAlpha setup is complete." in output
    assert "Run: py -m openalpha run ." in output
    assert r"Optional shell activation:" in output


def test_run_app_requires_frontend_dependencies(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    (frontend_dir / "package.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr("openalpha.cli.shutil.which", lambda _: "C:/Program Files/nodejs/npm.cmd")

    result = run_app(SimpleNamespace(path=str(tmp_path)))
    output = capsys.readouterr().out

    assert result == 1
    assert "Run `openalpha setup .` first." in output


def test_run_app_reexecs_into_project_virtualenv(monkeypatch, tmp_path) -> None:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    (frontend_dir / "package.json").write_text("{}", encoding="utf-8")

    venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")

    calls: list[tuple[list[str], Path, dict[str, str] | None]] = []

    def fake_run(command: list[str], *, cwd: Path | None = None, check: bool, env=None) -> SimpleNamespace:
        calls.append((command, cwd, env))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("openalpha.cli.subprocess.run", fake_run)
    monkeypatch.setattr("openalpha.cli.sys.executable", "C:/Python313/python.exe")
    monkeypatch.delenv("OPENALPHA_CLI_REEXEC", raising=False)

    result = run_app(SimpleNamespace(path=str(tmp_path)))

    assert result == 0
    assert len(calls) == 1
    command, cwd, env = calls[0]
    assert command == [str(venv_python), "-m", "openalpha.cli", "run", str(tmp_path)]
    assert cwd == tmp_path
    assert env is not None
    assert env["OPENALPHA_CLI_REEXEC"] == "1"
