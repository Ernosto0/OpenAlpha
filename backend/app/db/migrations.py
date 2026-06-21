from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Engine, text


MIGRATIONS: tuple[tuple[str, Iterable[str]], ...] = (
    (
        "0001_initial_sqlite_schema",
        (
            """
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR(120) NOT NULL PRIMARY KEY,
                value_json JSON NOT NULL DEFAULT '{}',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS analysis_runs (
                id VARCHAR(32) NOT NULL PRIMARY KEY,
                symbol VARCHAR(32) NOT NULL,
                market VARCHAR(32) NOT NULL,
                horizon VARCHAR(64) NOT NULL,
                depth VARCHAR(64) NOT NULL,
                language VARCHAR(16) NOT NULL DEFAULT 'en',
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                started_at DATETIME NOT NULL,
                finished_at DATETIME,
                total_cost_usd FLOAT NOT NULL DEFAULT 0,
                data_quality_score FLOAT,
                error_message VARCHAR
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS agent_outputs (
                id VARCHAR(32) NOT NULL PRIMARY KEY,
                analysis_run_id VARCHAR(32) NOT NULL,
                agent_name VARCHAR(120) NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                output_json JSON,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd FLOAT NOT NULL DEFAULT 0,
                started_at DATETIME NOT NULL,
                finished_at DATETIME,
                error_message VARCHAR,
                FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs (id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS reports (
                id VARCHAR(32) NOT NULL PRIMARY KEY,
                analysis_run_id VARCHAR(32) NOT NULL,
                symbol VARCHAR(32) NOT NULL,
                market VARCHAR(32) NOT NULL,
                horizon VARCHAR(64) NOT NULL,
                overall_view VARCHAR(64) NOT NULL,
                confidence FLOAT,
                risk_level VARCHAR(64),
                report_json JSON NOT NULL DEFAULT '{}',
                created_at DATETIME NOT NULL,
                FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs (id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS cost_traces (
                id VARCHAR(32) NOT NULL PRIMARY KEY,
                analysis_run_id VARCHAR(32) NOT NULL,
                agent_name VARCHAR(120) NOT NULL,
                provider VARCHAR(64) NOT NULL,
                model VARCHAR(120) NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd FLOAT NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs (id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_analysis_runs_symbol ON analysis_runs (symbol)",
            "CREATE INDEX IF NOT EXISTS ix_analysis_runs_market ON analysis_runs (market)",
            "CREATE INDEX IF NOT EXISTS ix_analysis_runs_status ON analysis_runs (status)",
            """
            CREATE INDEX IF NOT EXISTS ix_agent_outputs_analysis_run_id
            ON agent_outputs (analysis_run_id)
            """,
            "CREATE INDEX IF NOT EXISTS ix_agent_outputs_agent_name ON agent_outputs (agent_name)",
            "CREATE INDEX IF NOT EXISTS ix_agent_outputs_status ON agent_outputs (status)",
            "CREATE INDEX IF NOT EXISTS ix_reports_analysis_run_id ON reports (analysis_run_id)",
            "CREATE INDEX IF NOT EXISTS ix_reports_symbol ON reports (symbol)",
            "CREATE INDEX IF NOT EXISTS ix_reports_market ON reports (market)",
            """
            CREATE INDEX IF NOT EXISTS ix_cost_traces_analysis_run_id
            ON cost_traces (analysis_run_id)
            """,
            "CREATE INDEX IF NOT EXISTS ix_cost_traces_agent_name ON cost_traces (agent_name)",
        ),
    ),
)


def run_migrations(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(120) NOT NULL PRIMARY KEY,
                    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

        applied_versions = {
            row[0]
            for row in connection.execute(
                text("SELECT version FROM schema_migrations")
            ).all()
        }

        for version, statements in MIGRATIONS:
            if version in applied_versions:
                continue

            for statement in statements:
                connection.execute(text(statement))

            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": version},
            )
