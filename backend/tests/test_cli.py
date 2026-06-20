from __future__ import annotations

from openalpha.cli import _print_startup_message


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
