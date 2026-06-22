from __future__ import annotations

from fastapi import APIRouter

from backend.app.services.performance_service import (
    PerformanceResponse,
    performance_service,
)


router = APIRouter(tags=["performance"])


@router.get("/api/performance", response_model=PerformanceResponse)
async def get_performance() -> PerformanceResponse:
    return await performance_service.get_performance()
