from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    key: str = Field(primary_key=True, max_length=120)
    value_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class AnalysisRun(SQLModel, table=True):
    __tablename__ = "analysis_runs"

    id: str = Field(default_factory=new_id, primary_key=True, max_length=32)
    symbol: str = Field(index=True, max_length=32)
    market: str = Field(index=True, max_length=32)
    horizon: str = Field(max_length=64)
    depth: str = Field(max_length=64)
    language: str = Field(default="en", max_length=16)
    status: str = Field(default="pending", index=True, max_length=32)
    started_at: datetime = Field(default_factory=utc_now, nullable=False)
    finished_at: datetime | None = Field(default=None)
    total_cost_usd: float = Field(default=0.0)
    data_quality_score: float | None = Field(default=None)
    error_message: str | None = Field(default=None)

    agent_outputs: list["AgentOutput"] = Relationship(back_populates="analysis_run")
    reports: list["Report"] = Relationship(back_populates="analysis_run")
    cost_traces: list["CostTrace"] = Relationship(back_populates="analysis_run")


class AgentOutput(SQLModel, table=True):
    __tablename__ = "agent_outputs"

    id: str = Field(default_factory=new_id, primary_key=True, max_length=32)
    analysis_run_id: str = Field(foreign_key="analysis_runs.id", index=True)
    agent_name: str = Field(index=True, max_length=120)
    status: str = Field(default="pending", index=True, max_length=32)
    output_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    started_at: datetime = Field(default_factory=utc_now, nullable=False)
    finished_at: datetime | None = Field(default=None)
    error_message: str | None = Field(default=None)

    analysis_run: AnalysisRun = Relationship(back_populates="agent_outputs")


class Report(SQLModel, table=True):
    __tablename__ = "reports"

    id: str = Field(default_factory=new_id, primary_key=True, max_length=32)
    analysis_run_id: str = Field(foreign_key="analysis_runs.id", index=True)
    symbol: str = Field(index=True, max_length=32)
    market: str = Field(index=True, max_length=32)
    horizon: str = Field(max_length=64)
    overall_view: str = Field(max_length=64)
    confidence: float | None = Field(default=None)
    risk_level: str | None = Field(default=None, max_length=64)
    report_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, nullable=False)

    analysis_run: AnalysisRun = Relationship(back_populates="reports")


class CostTrace(SQLModel, table=True):
    __tablename__ = "cost_traces"

    id: str = Field(default_factory=new_id, primary_key=True, max_length=32)
    analysis_run_id: str = Field(foreign_key="analysis_runs.id", index=True)
    agent_name: str = Field(index=True, max_length=120)
    provider: str = Field(max_length=64)
    model: str = Field(max_length=120)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)

    analysis_run: AnalysisRun = Relationship(back_populates="cost_traces")
