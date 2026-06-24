from __future__ import annotations

import urllib.error

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.main import create_app
from backend.app.services.settings_service import SettingsService


def build_test_service(*, should_fail: bool = False) -> SettingsService:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session_factory = lambda: Session(engine)

    def transport(_url: str, _headers: dict[str, str], _timeout: float) -> str:
        if should_fail:
            raise urllib.error.URLError("invalid credentials")
        return '{"object":"list","data":[]}'

    async def ollama_transport(
        method: str,
        url: str,
        _headers: dict[str, str],
        _payload: dict | None,
        _timeout: float,
    ) -> dict:
        if should_fail:
            raise urllib.error.URLError("connection refused")
        if method == "GET" and url.endswith("/api/tags"):
            return {
                "models": [
                    {
                        "name": "llama3.1",
                        "model": "llama3.1",
                        "size": 123,
                        "details": {"family": "llama", "parameter_size": "8B"},
                    }
                ]
            }
        return {"message": {"content": "ok"}}

    return SettingsService(
        session_factory=session_factory,
        openai_test_transport=transport,
        claude_test_transport=transport,
        gemini_test_transport=transport,
        ollama_transport=ollama_transport,
    )


@pytest.mark.anyio
async def test_settings_endpoints_return_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    service = build_test_service()
    monkeypatch.setattr("backend.app.api.routes.settings.settings_service", service)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/settings")

    assert response.status_code == 200
    data = response.json()
    assert data["default_provider"] == "openai"
    assert data["default_model"] == "gpt-4.1-mini"
    assert data["providers"]["openai"]["api_key_configured"] is False
    assert data["providers"]["claude"]["api_key_configured"] is False
    assert data["providers"]["gemini"]["api_key_configured"] is False
    assert data["providers"]["ollama"]["base_url"] == "http://localhost:11434"


@pytest.mark.anyio
async def test_settings_save_and_preserve_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    service = build_test_service()
    monkeypatch.setattr("backend.app.api.routes.settings.settings_service", service)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        save_response = await client.put(
            "/api/settings",
            json={
                "default_provider": "claude",
                "default_model": "claude-3-5-sonnet-latest",
                "openai_api_key": "sk-test-12345678",
                "anthropic_api_key": "sk-ant-12345678",
                "gemini_api_key": "AIza-12345678",
                "ollama_base_url": "http://127.0.0.1:11434/",
                "ollama_model": "llama3.1",
            },
        )
        second_save_response = await client.put(
            "/api/settings",
            json={
                "default_provider": "gemini",
                "default_model": "gemini-2.5-pro",
                "openai_api_key": None,
                "anthropic_api_key": None,
                "gemini_api_key": None,
                "ollama_base_url": "http://127.0.0.1:11434",
                "ollama_model": "llama3.2",
            },
        )
        read_response = await client.get("/api/settings")

    assert save_response.status_code == 200
    assert second_save_response.status_code == 200
    data = read_response.json()
    assert data["default_provider"] == "gemini"
    assert data["default_model"] == "gemini-2.5-pro"
    assert data["providers"]["openai"]["api_key_configured"] is True
    assert data["providers"]["claude"]["api_key_configured"] is True
    assert data["providers"]["gemini"]["api_key_configured"] is True
    assert data["providers"]["openai"]["api_key_masked"] == "sk-t...5678"
    assert data["providers"]["claude"]["api_key_masked"] == "sk-a...5678"
    assert data["providers"]["gemini"]["api_key_masked"] == "AIza...5678"
    assert data["providers"]["ollama"]["base_url"] == "http://127.0.0.1:11434"
    assert data["providers"]["ollama"]["model"] == "llama3.2"
    assert {item["provider"] for item in data["configured_providers"]} == {
        "openai",
        "claude",
        "gemini",
        "ollama",
    }


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ["openai", "claude", "gemini"])
async def test_remote_provider_test_success(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    service = build_test_service()
    monkeypatch.setattr("backend.app.api.routes.settings.settings_service", service)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.put(
            "/api/settings",
            json={
                "default_provider": "openai",
                "default_model": "gpt-4.1-mini",
                "openai_api_key": "sk-live-12345678",
                "anthropic_api_key": "sk-ant-live-12345678",
                "gemini_api_key": "AIza-live-12345678",
                "ollama_base_url": "http://localhost:11434",
                "ollama_model": "llama3",
            },
        )
        test_response = await client.post(
            "/api/providers/llm/test",
            json={"provider": provider},
        )

    assert test_response.status_code == 200
    data = test_response.json()
    assert data["provider"] == provider
    assert data["success"] is True
    assert data["status"] == "tested"


@pytest.mark.anyio
async def test_provider_tests_handle_missing_and_ollama_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    service = build_test_service(should_fail=True)
    monkeypatch.setattr("backend.app.api.routes.settings.settings_service", service)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        missing_response = await client.post(
            "/api/providers/llm/test",
            json={"provider": "claude"},
        )
        local_response = await client.post(
            "/api/providers/llm/test",
            json={"provider": "ollama"},
        )

    assert missing_response.status_code == 200
    assert missing_response.json()["status"] == "missing"
    assert local_response.status_code == 200
    assert local_response.json()["status"] == "failed"


@pytest.mark.anyio
async def test_ollama_models_endpoint_returns_live_models(monkeypatch: pytest.MonkeyPatch) -> None:
    service = build_test_service()
    monkeypatch.setattr("backend.app.api.routes.settings.settings_service", service)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/providers/llm/ollama/models")

    assert response.status_code == 200
    data = response.json()
    assert data[0]["id"] == "llama3.1"
