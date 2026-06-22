from __future__ import annotations

from fastapi import APIRouter

from backend.app.services.settings_service import (
    AppSettingsResponse,
    AppSettingsUpdate,
    ProviderTestRequest,
    ProviderTestResponse,
    settings_service,
)


router = APIRouter(tags=["settings"])


@router.get("/api/settings", response_model=AppSettingsResponse)
async def get_settings() -> AppSettingsResponse:
    return settings_service.get_settings()


@router.put("/api/settings", response_model=AppSettingsResponse)
async def save_settings(payload: AppSettingsUpdate) -> AppSettingsResponse:
    return settings_service.save_settings(payload)


@router.post("/api/providers/llm/test", response_model=ProviderTestResponse)
async def test_llm_provider(payload: ProviderTestRequest) -> ProviderTestResponse:
    return settings_service.test_provider(payload)
