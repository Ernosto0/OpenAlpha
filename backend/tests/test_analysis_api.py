from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.main import create_app
from backend.app.orchestrator.base import AnalysisEvent, AnalysisEventEmitter
from backend.app.orchestrator.schemas import AnalysisRequest
from backend.app.services.analysis_manager import AnalysisManager
from backend.app.db.models import AgentOutput, AnalysisRun, Report


class StubRunner:
    def __init__(self, emitter: AnalysisEventEmitter, session_factory) -> None:
        self.emitter = emitter
        self.session_factory = session_factory

    async def run(
        self, request: AnalysisRequest, run_id: str | None = None
    ) -> None:
        assert run_id is not None
        started_at = datetime.now(timezone.utc)
        finished_at = datetime.now(timezone.utc)

        with self.session_factory() as session:
            run = session.get(AnalysisRun, run_id)
            assert run is not None
            run.status = "running"
            run.started_at = started_at
            session.add(run)
            session.commit()

        self.emitter.emit(
            AnalysisEvent(
                type="analysis_started",
                run_id=run_id,
                timestamp=started_at,
                status="running",
                message=f"Analysis started for {request.symbol}.",
            )
        )
        self.emitter.emit(
            AnalysisEvent(
                type="agent_started",
                run_id=run_id,
                timestamp=started_at,
                agent_name="data_collector",
                status="running",
                message="data_collector started.",
            )
        )

        with self.session_factory() as session:
            session.add(
                AgentOutput(
                    analysis_run_id=run_id,
                    agent_name="data_collector",
                    status="completed",
                    output_json={"market_data": {"symbol": request.symbol}},
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0,
                    started_at=started_at,
                    finished_at=finished_at,
                )
            )
            session.add(
                Report(
                    analysis_run_id=run_id,
                    symbol=request.symbol,
                    market=request.market,
                    horizon=request.horizon,
                    overall_view="neutral",
                    confidence=0.55,
                    risk_level="moderate",
                    report_json={"symbol": request.symbol, "overall_view": "neutral"},
                    created_at=finished_at,
                )
            )
            run = session.get(AnalysisRun, run_id)
            assert run is not None
            run.status = "completed"
            run.total_cost_usd = 0.028
            run.finished_at = finished_at
            session.add(run)
            session.commit()

        self.emitter.emit(
            AnalysisEvent(
                type="agent_finished",
                run_id=run_id,
                timestamp=finished_at,
                agent_name="data_collector",
                status="completed",
                message="data_collector completed.",
            )
        )
        self.emitter.emit(
            AnalysisEvent(
                type="analysis_completed",
                run_id=run_id,
                timestamp=finished_at,
                status="completed",
                message=f"Analysis completed for {request.symbol}.",
            )
        )


def build_test_manager() -> AnalysisManager:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session_factory = lambda: Session(engine)
    return AnalysisManager(
        session_factory=session_factory,
        runner_factory=lambda emitter: StubRunner(emitter, session_factory),
    )


async def wait_for_completion(client: httpx.AsyncClient, run_id: str) -> dict:
    for _ in range(20):
        response = await client.get(f"/api/analysis/{run_id}")
        if response.status_code == 200 and response.json()["status"] == "completed":
            return response.json()
        await asyncio.sleep(0.01)
    raise AssertionError("analysis run did not complete in time")


@pytest.mark.anyio
async def test_analysis_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = build_test_manager()
    monkeypatch.setattr("backend.app.api.routes.analysis.analysis_manager", manager)
    monkeypatch.setattr(
        "backend.app.api.routes.analysis.settings_service.get_settings",
        lambda: SimpleNamespace(
            providers=SimpleNamespace(
                openai=SimpleNamespace(api_key_configured=True),
                claude=SimpleNamespace(api_key_configured=True),
                gemini=SimpleNamespace(api_key_configured=True),
            )
        ),
    )

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    request_payload = {
        "symbol": "AAPL",
        "market": "US",
        "horizon": "3m",
        "depth": "standard",
        "language": "en",
        "llm_provider": "openai",
        "llm_model": "gpt-4.1-mini",
        "custom_question": "Focus on earnings risk.",
    }

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        create_response = await client.post("/api/analysis/run", json=request_payload)
        assert create_response.status_code == 200
        create_data = create_response.json()
        assert create_data["status"] == "running"

        detail_data = await wait_for_completion(client, create_data["run_id"])
        assert detail_data["symbol"] == "AAPL"
        assert detail_data["horizon"] == "3m"
        assert detail_data["total_cost_usd"] == 0.028
        assert len(detail_data["agent_outputs"]) == 1
        assert detail_data["report_id"] is not None

        events_response = await client.get(
            f"/api/analysis/{create_data['run_id']}/events"
        )
        assert events_response.status_code == 200
        events_data = events_response.json()
        assert events_data["run_id"] == create_data["run_id"]
        assert [event["type"] for event in events_data["events"]] == [
            "analysis_started",
            "agent_started",
            "agent_finished",
            "analysis_completed",
        ]


@pytest.mark.anyio
async def test_analysis_run_requires_openai_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = build_test_manager()
    monkeypatch.setattr("backend.app.api.routes.analysis.analysis_manager", manager)
    monkeypatch.setattr(
        "backend.app.api.routes.analysis.settings_service.get_settings",
        lambda: SimpleNamespace(
            providers=SimpleNamespace(
                openai=SimpleNamespace(api_key_configured=False),
                claude=SimpleNamespace(api_key_configured=True),
                gemini=SimpleNamespace(api_key_configured=True),
            )
        ),
    )

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    request_payload = {
        "symbol": "AAPL",
        "market": "US",
        "horizon": "3m",
        "depth": "standard",
        "language": "en",
        "llm_provider": "openai",
        "llm_model": "gpt-4.1-mini",
        "custom_question": None,
    }

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        create_response = await client.post("/api/analysis/run", json=request_payload)

    assert create_response.status_code == 400
    assert (
        create_response.json()["detail"]
        == "OpenAI API key is missing. Add it in Settings before running analysis."
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("provider", "detail"),
    [
        (
            "claude",
            "Claude API key is missing. Add it in Settings before running analysis.",
        ),
        (
            "gemini",
            "Gemini API key is missing. Add it in Settings before running analysis.",
        ),
    ],
)
async def test_analysis_run_requires_remote_provider_key(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    detail: str,
) -> None:
    manager = build_test_manager()
    monkeypatch.setattr("backend.app.api.routes.analysis.analysis_manager", manager)
    monkeypatch.setattr(
        "backend.app.api.routes.analysis.settings_service.get_settings",
        lambda: SimpleNamespace(
            providers=SimpleNamespace(
                openai=SimpleNamespace(api_key_configured=True),
                claude=SimpleNamespace(api_key_configured=provider != "claude"),
                gemini=SimpleNamespace(api_key_configured=provider != "gemini"),
            )
        ),
    )

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    request_payload = {
        "symbol": "AAPL",
        "market": "US",
        "horizon": "3m",
        "depth": "standard",
        "language": "en",
        "llm_provider": provider,
        "llm_model": "test-model",
        "custom_question": None,
    }

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        create_response = await client.post("/api/analysis/run", json=request_payload)

    assert create_response.status_code == 400
    assert create_response.json()["detail"] == detail


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("claude", "claude-3-5-sonnet-latest"),
        ("gemini", "gemini-2.5-pro"),
    ],
)
async def test_analysis_run_accepts_configured_remote_provider(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    model: str,
) -> None:
    manager = build_test_manager()
    monkeypatch.setattr("backend.app.api.routes.analysis.analysis_manager", manager)
    monkeypatch.setattr(
        "backend.app.api.routes.analysis.settings_service.get_settings",
        lambda: SimpleNamespace(
            providers=SimpleNamespace(
                openai=SimpleNamespace(api_key_configured=True),
                claude=SimpleNamespace(api_key_configured=True),
                gemini=SimpleNamespace(api_key_configured=True),
            )
        ),
    )

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    request_payload = {
        "symbol": "AAPL",
        "market": "US",
        "horizon": "3m",
        "depth": "standard",
        "language": "en",
        "llm_provider": provider,
        "llm_model": model,
        "custom_question": None,
    }

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        create_response = await client.post("/api/analysis/run", json=request_payload)

    assert create_response.status_code == 200
    assert create_response.json()["status"] == "running"


@pytest.mark.anyio
async def test_analysis_run_accepts_ollama_when_runtime_and_model_are_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = build_test_manager()
    monkeypatch.setattr("backend.app.api.routes.analysis.analysis_manager", manager)
    monkeypatch.setattr(
        "backend.app.api.routes.analysis.settings_service.get_ollama_runtime_config",
        lambda **_kwargs: ("http://localhost:11434", "llama3.1"),
    )
    monkeypatch.setattr(
        "backend.app.api.routes.analysis.settings_service.build_ollama_provider",
        lambda **_kwargs: SimpleNamespace(
            health_check=lambda: asyncio.sleep(0, result=SimpleNamespace(available=True, message="ok")),
            list_models=lambda: asyncio.sleep(
                0,
                result=[SimpleNamespace(id="llama3.1")],
            ),
        ),
    )

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    request_payload = {
        "symbol": "AAPL",
        "market": "US",
        "horizon": "3m",
        "depth": "standard",
        "language": "en",
        "llm_provider": "ollama",
        "llm_model": "llama3.1",
        "custom_question": None,
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_response = await client.post("/api/analysis/run", json=request_payload)

    assert create_response.status_code == 200
    assert create_response.json()["status"] == "running"


@pytest.mark.anyio
async def test_analysis_run_rejects_missing_ollama_model_before_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = build_test_manager()
    monkeypatch.setattr("backend.app.api.routes.analysis.analysis_manager", manager)
    monkeypatch.setattr(
        "backend.app.api.routes.analysis.settings_service.get_ollama_runtime_config",
        lambda **_kwargs: ("http://localhost:11434", "llama3.2"),
    )
    monkeypatch.setattr(
        "backend.app.api.routes.analysis.settings_service.build_ollama_provider",
        lambda **_kwargs: SimpleNamespace(
            health_check=lambda: asyncio.sleep(0, result=SimpleNamespace(available=True, message="ok")),
            list_models=lambda: asyncio.sleep(
                0,
                result=[SimpleNamespace(id="llama3.1")],
            ),
        ),
    )

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    request_payload = {
        "symbol": "AAPL",
        "market": "US",
        "horizon": "3m",
        "depth": "standard",
        "language": "en",
        "llm_provider": "ollama",
        "llm_model": "llama3.2",
        "custom_question": None,
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_response = await client.post("/api/analysis/run", json=request_payload)

    assert create_response.status_code == 400
    assert "selected model 'llama3.2' is unavailable" in create_response.json()["detail"]


@pytest.mark.anyio
async def test_analysis_endpoints_return_404_for_missing_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = build_test_manager()
    monkeypatch.setattr("backend.app.api.routes.analysis.analysis_manager", manager)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        detail_response = await client.get("/api/analysis/does-not-exist")
        events_response = await client.get("/api/analysis/does-not-exist/events")

    assert detail_response.status_code == 404
    assert events_response.status_code == 404
