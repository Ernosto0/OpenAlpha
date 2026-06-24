from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket

from backend.app.llm.base import (
    LLMConfigurationError,
    LLMProviderError,
    normalize_provider_name,
)
from backend.app.orchestrator.schemas import AnalysisRequest
from backend.app.services.settings_service import settings_service
from backend.app.services.analysis_manager import (
    AnalysisRunAcceptedResponse,
    AnalysisRunDetailResponse,
    AnalysisRunEventsResponse,
    analysis_manager,
)


router = APIRouter(tags=["analysis"])


@router.post("/api/analysis/run", response_model=AnalysisRunAcceptedResponse)
async def run_analysis(
    request: AnalysisRequest,
) -> AnalysisRunAcceptedResponse:
    provider = normalize_provider_name(request.llm_provider)
    if provider in {"openai", "claude", "gemini"}:
        settings = settings_service.get_settings()
        provider_settings = getattr(settings.providers, provider)
        if not provider_settings.api_key_configured:
            labels = {
                "openai": "OpenAI",
                "claude": "Claude",
                "gemini": "Gemini",
            }
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{labels[provider]} API key is missing. "
                    "Add it in Settings before running analysis."
                ),
            )
    if provider == "ollama":
        try:
            base_url, resolved_model = settings_service.get_ollama_runtime_config(
                model=request.llm_model,
            )
            ollama_provider = settings_service.build_ollama_provider(
                base_url=base_url,
                model=resolved_model,
            )
            health = await ollama_provider.health_check()
            if not health.available:
                raise HTTPException(status_code=400, detail=health.message)
            models = await ollama_provider.list_models()
            if not models:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Ollama is connected at {base_url}, but no models are installed. "
                        "Pull a model before starting analysis."
                    ),
                )
            if not any(model.id == resolved_model for model in models):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Ollama is connected at {base_url}, but the selected model "
                        f"'{resolved_model}' is unavailable."
                    ),
                )
        except (LLMConfigurationError, LLMProviderError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await analysis_manager.start_run(request)


@router.get(
    "/api/analysis/{run_id}",
    response_model=AnalysisRunDetailResponse,
)
async def get_analysis_run(run_id: str) -> AnalysisRunDetailResponse:
    detail = await analysis_manager.get_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    return detail


@router.get(
    "/api/analysis/{run_id}/events",
    response_model=AnalysisRunEventsResponse,
)
async def get_analysis_events(run_id: str) -> AnalysisRunEventsResponse:
    events = await analysis_manager.get_events(run_id)
    if events is None:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    return events


@router.websocket("/ws/analysis/{run_id}")
async def analysis_events_websocket(websocket: WebSocket, run_id: str) -> None:
    await analysis_manager.stream_events(run_id, websocket)
