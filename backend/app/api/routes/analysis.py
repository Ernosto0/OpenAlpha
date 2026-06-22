from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket

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
    if request.llm_provider.strip().lower() == "openai":
        settings = settings_service.get_settings()
        if not settings.providers["openai"].api_key_configured:
            raise HTTPException(
                status_code=400,
                detail="OpenAI API key is missing. Add it in Settings before running analysis.",
            )
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
