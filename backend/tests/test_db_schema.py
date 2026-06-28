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

    agent_output_columns = {column["name"] for column in inspector.get_columns("agent_outputs")}
    cost_trace_columns = {column["name"] for column in inspector.get_columns("cost_traces")}

    assert {"provider", "model", "cost_type", "warnings_json", "parsing_errors_json", "duration_ms"} <= agent_output_columns
    assert {"cost_type", "warnings_json", "parsing_errors_json", "duration_ms"} <= cost_trace_columns


def test_initial_migration_records_applied_version(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'openalpha.db'}"
    engine = create_engine(database_url)

    run_migrations(engine)
    run_migrations(engine)

    with engine.connect() as connection:
        rows = connection.exec_driver_sql(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).all()

    assert rows == [
        ("0001_initial_sqlite_schema",),
        ("0002_enrich_llm_telemetry",),
    ]


def test_followup_migration_skips_columns_that_already_exist(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'openalpha.db'}"
    engine = create_engine(database_url)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(120) NOT NULL PRIMARY KEY,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO schema_migrations (version) VALUES ('0001_initial_sqlite_schema')"
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE agent_outputs (
                id VARCHAR(32) NOT NULL PRIMARY KEY,
                analysis_run_id VARCHAR(32) NOT NULL,
                agent_name VARCHAR(120) NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                provider VARCHAR(64) NOT NULL DEFAULT 'deterministic',
                model VARCHAR(120) NOT NULL DEFAULT 'deterministic',
                output_json JSON,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd FLOAT NOT NULL DEFAULT 0,
                cost_type VARCHAR(64) NOT NULL DEFAULT 'api',
                warnings_json JSON NOT NULL DEFAULT '[]',
                parsing_errors_json JSON NOT NULL DEFAULT '[]',
                duration_ms INTEGER NOT NULL DEFAULT 0,
                started_at DATETIME NOT NULL,
                finished_at DATETIME,
                error_message VARCHAR
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE cost_traces (
                id VARCHAR(32) NOT NULL PRIMARY KEY,
                analysis_run_id VARCHAR(32) NOT NULL,
                agent_name VARCHAR(120) NOT NULL,
                provider VARCHAR(64) NOT NULL,
                model VARCHAR(120) NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd FLOAT NOT NULL DEFAULT 0,
                cost_type VARCHAR(64) NOT NULL DEFAULT 'api',
                duration_ms INTEGER NOT NULL DEFAULT 0,
                warnings_json JSON NOT NULL DEFAULT '[]',
                parsing_errors_json JSON NOT NULL DEFAULT '[]',
                created_at DATETIME NOT NULL
            )
            """
        )

    run_migrations(engine)

    with engine.connect() as connection:
        rows = connection.exec_driver_sql(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).all()

    assert rows == [
        ("0001_initial_sqlite_schema",),
        ("0002_enrich_llm_telemetry",),
    ]
