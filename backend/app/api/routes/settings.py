from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.llm import LLMModelInfo
from backend.app.llm.base import LLMConfigurationError, LLMProviderError
from backend.app.services.settings_service import (
    AppSettingsResponse,
    AppSettingsUpdate,
    ProviderCatalogEntry,
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


@router.get("/api/providers", response_model=list[ProviderCatalogEntry])
async def list_providers() -> list[ProviderCatalogEntry]:
    return settings_service.list_provider_catalog()


@router.post("/api/providers/llm/test", response_model=ProviderTestResponse)
async def test_llm_provider(payload: ProviderTestRequest) -> ProviderTestResponse:
    return await settings_service.test_provider(payload)


@router.get("/api/providers/llm/ollama/models", response_model=list[dict])
async def list_ollama_models(
    base_url: str | None = Query(default=None, max_length=300),
) -> list[LLMModelInfo]:
    try:
        return await settings_service.list_ollama_models(base_url=base_url)
    except (LLMConfigurationError, LLMProviderError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
