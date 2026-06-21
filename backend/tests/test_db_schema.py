from __future__ import annotations

from sqlalchemy import inspect
from sqlmodel import create_engine

from backend.app.db.migrations import run_migrations


def test_initial_migration_creates_phase_three_tables(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'openalpha.db'}"
    engine = create_engine(database_url)

    run_migrations(engine)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert "schema_migrations" in table_names
    assert "settings" in table_names
    assert "analysis_runs" in table_names
    assert "agent_outputs" in table_names
    assert "reports" in table_names
    assert "cost_traces" in table_names


def test_initial_migration_records_applied_version(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'openalpha.db'}"
    engine = create_engine(database_url)

    run_migrations(engine)
    run_migrations(engine)

    with engine.connect() as connection:
        rows = connection.exec_driver_sql(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).all()

    assert rows == [("0001_initial_sqlite_schema",)]
