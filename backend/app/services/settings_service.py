from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, Literal

from pydantic import Field
from sqlmodel import Session

from backend.app.db.models import Setting
from backend.app.db.session import engine
from backend.app.orchestrator.schemas import OpenAlphaSchema, utc_now


SettingsProvider = Literal["openai", "local"]
ProviderTestStatus = Literal["configured", "missing", "tested", "failed", "untested"]
ProviderTestable = Literal["openai", "local"]

SETTINGS_KEY = "app_settings"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_OLLAMA_MODEL = "llama3"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


class ConfiguredProviderSummary(OpenAlphaSchema):
    provider: SettingsProvider
    label: str
    status: ProviderTestStatus
    model: str | None = None


class OpenAIProviderSettings(OpenAlphaSchema):
    api_key_configured: bool = False
    api_key_masked: str | None = None
    status: ProviderTestStatus = "missing"
    last_test_message: str | None = None
    last_tested_at: datetime | None = None


class OllamaProviderSettings(OpenAlphaSchema):
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    model: str = DEFAULT_OLLAMA_MODEL
    status: ProviderTestStatus = "untested"
    last_test_message: str | None = None
    last_tested_at: datetime | None = None


class AppSettingsResponse(OpenAlphaSchema):
    default_provider: SettingsProvider = "openai"
    default_model: str = DEFAULT_OPENAI_MODEL
    providers: dict[str, OpenAIProviderSettings | OllamaProviderSettings]
    configured_providers: list[ConfiguredProviderSummary] = Field(default_factory=list)


class AppSettingsUpdate(OpenAlphaSchema):
    default_provider: SettingsProvider
    default_model: str = Field(min_length=1, max_length=120)
    openai_api_key: str | None = Field(default=None, max_length=500)
    ollama_base_url: str = Field(min_length=1, max_length=300)
    ollama_model: str = Field(min_length=1, max_length=120)


class ProviderTestRequest(OpenAlphaSchema):
    provider: ProviderTestable


class ProviderTestResponse(OpenAlphaSchema):
    provider: ProviderTestable
    success: bool
    status: ProviderTestStatus
    message: str
    tested_at: datetime = Field(default_factory=utc_now)


class SettingsService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
        openai_test_transport: Callable[[str, Mapping[str, str], float], str] | None = None,
    ) -> None:
        self._session_factory = session_factory or (lambda: Session(engine))
        self._openai_test_transport = openai_test_transport or self._default_openai_test_transport

    def get_settings(self) -> AppSettingsResponse:
        with self._session_factory() as session:
            payload = self._load_payload(session)
            return self._build_response(payload)

    def save_settings(self, update: AppSettingsUpdate) -> AppSettingsResponse:
        with self._session_factory() as session:
            payload = self._load_payload(session)
            payload["default_provider"] = update.default_provider
            payload["default_model"] = update.default_model.strip()
            if update.openai_api_key is not None:
                payload["openai_api_key"] = self._normalize_secret(update.openai_api_key)
            payload["ollama_base_url"] = update.ollama_base_url.strip().rstrip("/")
            payload["ollama_model"] = update.ollama_model.strip()
            self._save_payload(session, payload)
            return self._build_response(payload)

    def test_provider(self, request: ProviderTestRequest) -> ProviderTestResponse:
        with self._session_factory() as session:
            payload = self._load_payload(session)
            tested_at = utc_now()
            if request.provider == "openai":
                response = self._test_openai(payload, tested_at)
            else:
                response = ProviderTestResponse(
                    provider="local",
                    success=False,
                    status="untested",
                    message="Ollama live testing is not implemented in this version.",
                    tested_at=tested_at,
                )

            test_results = payload.setdefault("provider_test_results", {})
            test_results[request.provider] = {
                "status": response.status,
                "message": response.message,
                "tested_at": response.tested_at.isoformat(),
            }
            self._save_payload(session, payload)
            return response

    def _test_openai(
        self,
        payload: dict[str, Any],
        tested_at: datetime,
    ) -> ProviderTestResponse:
        api_key = self._normalize_secret(payload.get("openai_api_key"))
        if not api_key:
            return ProviderTestResponse(
                provider="openai",
                success=False,
                status="missing",
                message="OpenAI API key is missing.",
                tested_at=tested_at,
            )

        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            self._openai_test_transport("https://api.openai.com/v1/models", headers, 15.0)
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace").strip() or f"HTTP {exc.code}"
            return ProviderTestResponse(
                provider="openai",
                success=False,
                status="failed",
                message=f"OpenAI test failed: {message}",
                tested_at=tested_at,
            )
        except urllib.error.URLError as exc:
            return ProviderTestResponse(
                provider="openai",
                success=False,
                status="failed",
                message=f"OpenAI test failed: {exc.reason}",
                tested_at=tested_at,
            )
        except Exception as exc:
            return ProviderTestResponse(
                provider="openai",
                success=False,
                status="failed",
                message=f"OpenAI test failed: {exc}",
                tested_at=tested_at,
            )

        return ProviderTestResponse(
            provider="openai",
            success=True,
            status="tested",
            message="OpenAI credentials are valid.",
            tested_at=tested_at,
        )

    def _default_openai_test_transport(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> str:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8")

    def _load_payload(self, session: Session) -> dict[str, Any]:
        row = session.get(Setting, SETTINGS_KEY)
        if row is None or not isinstance(row.value_json, dict):
            return self._default_payload()

        payload = self._default_payload()
        payload.update(row.value_json)
        payload["provider_test_results"] = self._normalize_test_results(
            row.value_json.get("provider_test_results")
        )
        return payload

    def _save_payload(self, session: Session, payload: dict[str, Any]) -> None:
        row = session.get(Setting, SETTINGS_KEY)
        now = utc_now()
        if row is None:
            row = Setting(
                key=SETTINGS_KEY,
                value_json=payload,
                created_at=now,
                updated_at=now,
            )
        else:
            row.value_json = payload
            row.updated_at = now
        session.add(row)
        session.commit()

    def _build_response(self, payload: dict[str, Any]) -> AppSettingsResponse:
        test_results = self._normalize_test_results(payload.get("provider_test_results"))
        openai_status = self._resolve_openai_status(payload, test_results)
        ollama_status = self._resolve_local_status(payload, test_results)

        openai_settings = OpenAIProviderSettings(
            api_key_configured=bool(self._normalize_secret(payload.get("openai_api_key"))),
            api_key_masked=self._mask_secret(payload.get("openai_api_key")),
            status=openai_status,
            last_test_message=test_results.get("openai", {}).get("message"),
            last_tested_at=self._parse_datetime(test_results.get("openai", {}).get("tested_at")),
        )
        ollama_settings = OllamaProviderSettings(
            base_url=str(payload.get("ollama_base_url") or DEFAULT_OLLAMA_BASE_URL),
            model=str(payload.get("ollama_model") or DEFAULT_OLLAMA_MODEL),
            status=ollama_status,
            last_test_message=test_results.get("local", {}).get("message"),
            last_tested_at=self._parse_datetime(test_results.get("local", {}).get("tested_at")),
        )

        return AppSettingsResponse(
            default_provider=self._coerce_provider(payload.get("default_provider")),
            default_model=str(payload.get("default_model") or DEFAULT_OPENAI_MODEL),
            providers={
                "openai": openai_settings,
                "local": ollama_settings,
            },
            configured_providers=self._configured_providers(openai_settings, ollama_settings),
        )

    def _configured_providers(
        self,
        openai_settings: OpenAIProviderSettings,
        ollama_settings: OllamaProviderSettings,
    ) -> list[ConfiguredProviderSummary]:
        providers: list[ConfiguredProviderSummary] = []
        if openai_settings.api_key_configured:
            providers.append(
                ConfiguredProviderSummary(
                    provider="openai",
                    label="OpenAI",
                    status=openai_settings.status,
                    model=None,
                )
            )
        if ollama_settings.base_url.strip():
            providers.append(
                ConfiguredProviderSummary(
                    provider="local",
                    label="Ollama",
                    status=ollama_settings.status,
                    model=ollama_settings.model,
                )
            )
        return providers

    def _resolve_openai_status(
        self,
        payload: dict[str, Any],
        test_results: dict[str, dict[str, str]],
    ) -> ProviderTestStatus:
        if not self._normalize_secret(payload.get("openai_api_key")):
            return "missing"
        status = test_results.get("openai", {}).get("status")
        return status if status in {"configured", "tested", "failed"} else "configured"

    def _resolve_local_status(
        self,
        payload: dict[str, Any],
        test_results: dict[str, dict[str, str]],
    ) -> ProviderTestStatus:
        if not str(payload.get("ollama_base_url") or "").strip():
            return "missing"
        status = test_results.get("local", {}).get("status")
        return status if status in {"configured", "tested", "failed", "untested"} else "untested"

    def _default_payload(self) -> dict[str, Any]:
        return {
            "default_provider": "openai",
            "default_model": DEFAULT_OPENAI_MODEL,
            "openai_api_key": None,
            "ollama_base_url": DEFAULT_OLLAMA_BASE_URL,
            "ollama_model": DEFAULT_OLLAMA_MODEL,
            "provider_test_results": {},
        }

    def _normalize_test_results(self, value: Any) -> dict[str, dict[str, str]]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, dict[str, str]] = {}
        for provider_name, result in value.items():
            if not isinstance(provider_name, str) or not isinstance(result, dict):
                continue
            entry: dict[str, str] = {}
            for key in ("status", "message", "tested_at"):
                item = result.get(key)
                if isinstance(item, str) and item.strip():
                    entry[key] = item.strip()
            normalized[provider_name] = entry
        return normalized

    def _normalize_secret(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None

    def _mask_secret(self, value: Any) -> str | None:
        secret = self._normalize_secret(value)
        if not secret:
            return None
        if len(secret) <= 8:
            return "*" * len(secret)
        return f"{secret[:4]}...{secret[-4:]}"

    def _coerce_provider(self, value: Any) -> SettingsProvider:
        return "local" if value == "local" else "openai"

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None


settings_service = SettingsService()


__all__ = [
    "AppSettingsResponse",
    "AppSettingsUpdate",
    "ConfiguredProviderSummary",
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OPENAI_MODEL",
    "OpenAIProviderSettings",
    "OllamaProviderSettings",
    "ProviderTestRequest",
    "ProviderTestResponse",
    "SettingsProvider",
    "SettingsService",
    "settings_service",
]
