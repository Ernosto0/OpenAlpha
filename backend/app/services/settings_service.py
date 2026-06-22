from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, Literal

from pydantic import Field
from sqlmodel import Session

from backend.app.db.models import Setting
from backend.app.db.session import engine
from backend.app.orchestrator.schemas import OpenAlphaSchema, utc_now


SettingsProvider = Literal["openai", "claude", "gemini", "local"]
ProviderTestStatus = Literal["configured", "missing", "tested", "failed", "untested"]
ProviderTestable = Literal["openai", "claude", "gemini", "local"]
ProviderTestTransport = Callable[[str, Mapping[str, str], float], str]

SETTINGS_KEY = "app_settings"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-latest"
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"
DEFAULT_OLLAMA_MODEL = "llama3"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"

PROVIDER_LABELS: dict[SettingsProvider, str] = {
    "openai": "OpenAI",
    "claude": "Claude",
    "gemini": "Gemini",
    "local": "Ollama",
}

REMOTE_PROVIDERS: tuple[SettingsProvider, ...] = ("openai", "claude", "gemini")
API_KEY_FIELDS: dict[Literal["openai", "claude", "gemini"], str] = {
    "openai": "openai_api_key",
    "claude": "anthropic_api_key",
    "gemini": "gemini_api_key",
}


class ConfiguredProviderSummary(OpenAlphaSchema):
    provider: SettingsProvider
    label: str
    status: ProviderTestStatus
    model: str | None = None


class RemoteProviderSettings(OpenAlphaSchema):
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


class AppSettingsProviders(OpenAlphaSchema):
    openai: RemoteProviderSettings
    claude: RemoteProviderSettings
    gemini: RemoteProviderSettings
    local: OllamaProviderSettings


class AppSettingsResponse(OpenAlphaSchema):
    default_provider: SettingsProvider = "openai"
    default_model: str = DEFAULT_OPENAI_MODEL
    providers: AppSettingsProviders
    configured_providers: list[ConfiguredProviderSummary] = Field(default_factory=list)


class AppSettingsUpdate(OpenAlphaSchema):
    default_provider: SettingsProvider
    default_model: str = Field(min_length=1, max_length=120)
    openai_api_key: str | None = Field(default=None, max_length=500)
    anthropic_api_key: str | None = Field(default=None, max_length=500)
    gemini_api_key: str | None = Field(default=None, max_length=500)
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
        openai_test_transport: ProviderTestTransport | None = None,
        claude_test_transport: ProviderTestTransport | None = None,
        gemini_test_transport: ProviderTestTransport | None = None,
    ) -> None:
        self._session_factory = session_factory or (lambda: Session(engine))
        self._provider_test_transports: dict[str, ProviderTestTransport] = {
            "openai": openai_test_transport or self._default_test_transport,
            "claude": claude_test_transport or self._default_test_transport,
            "gemini": gemini_test_transport or self._default_test_transport,
        }

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
            if update.anthropic_api_key is not None:
                payload["anthropic_api_key"] = self._normalize_secret(update.anthropic_api_key)
            if update.gemini_api_key is not None:
                payload["gemini_api_key"] = self._normalize_secret(update.gemini_api_key)
            payload["ollama_base_url"] = update.ollama_base_url.strip().rstrip("/")
            payload["ollama_model"] = update.ollama_model.strip()
            self._save_payload(session, payload)
            return self._build_response(payload)

    def test_provider(self, request: ProviderTestRequest) -> ProviderTestResponse:
        with self._session_factory() as session:
            payload = self._load_payload(session)
            tested_at = utc_now()

            if request.provider == "local":
                response = ProviderTestResponse(
                    provider="local",
                    success=False,
                    status="untested",
                    message="Ollama live testing is not implemented in this version.",
                    tested_at=tested_at,
                )
            else:
                response = self._test_remote_provider(
                    request.provider,
                    payload,
                    tested_at,
                )

            test_results = payload.setdefault("provider_test_results", {})
            test_results[request.provider] = {
                "status": response.status,
                "message": response.message,
                "tested_at": response.tested_at.isoformat(),
            }
            self._save_payload(session, payload)
            return response

    def _test_remote_provider(
        self,
        provider: Literal["openai", "claude", "gemini"],
        payload: dict[str, Any],
        tested_at: datetime,
    ) -> ProviderTestResponse:
        api_key = self._normalize_secret(payload.get(API_KEY_FIELDS[provider]))
        label = PROVIDER_LABELS[provider]
        if not api_key:
            return ProviderTestResponse(
                provider=provider,
                success=False,
                status="missing",
                message=f"{label} API key is missing.",
                tested_at=tested_at,
            )

        url, headers = self._build_provider_test_request(provider, api_key)
        transport = self._provider_test_transports[provider]
        try:
            transport(url, headers, 15.0)
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace").strip() or f"HTTP {exc.code}"
            return ProviderTestResponse(
                provider=provider,
                success=False,
                status="failed",
                message=f"{label} test failed: {message}",
                tested_at=tested_at,
            )
        except urllib.error.URLError as exc:
            return ProviderTestResponse(
                provider=provider,
                success=False,
                status="failed",
                message=f"{label} test failed: {exc.reason}",
                tested_at=tested_at,
            )
        except Exception as exc:
            return ProviderTestResponse(
                provider=provider,
                success=False,
                status="failed",
                message=f"{label} test failed: {exc}",
                tested_at=tested_at,
            )

        return ProviderTestResponse(
            provider=provider,
            success=True,
            status="tested",
            message=f"{label} credentials are valid.",
            tested_at=tested_at,
        )

    def _build_provider_test_request(
        self,
        provider: Literal["openai", "claude", "gemini"],
        api_key: str,
    ) -> tuple[str, dict[str, str]]:
        if provider == "openai":
            return (
                "https://api.openai.com/v1/models",
                {"Authorization": f"Bearer {api_key}"},
            )
        if provider == "claude":
            return (
                "https://api.anthropic.com/v1/models",
                {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
        encoded_key = urllib.parse.quote(api_key, safe="")
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models?key={encoded_key}",
            {},
        )

    def _default_test_transport(
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
        remote_settings = {
            provider: self._build_remote_provider_settings(payload, test_results, provider)
            for provider in REMOTE_PROVIDERS
        }
        local_settings = OllamaProviderSettings(
            base_url=str(payload.get("ollama_base_url") or DEFAULT_OLLAMA_BASE_URL),
            model=str(payload.get("ollama_model") or DEFAULT_OLLAMA_MODEL),
            status=self._resolve_local_status(payload, test_results),
            last_test_message=test_results.get("local", {}).get("message"),
            last_tested_at=self._parse_datetime(test_results.get("local", {}).get("tested_at")),
        )

        return AppSettingsResponse(
            default_provider=self._coerce_provider(payload.get("default_provider")),
            default_model=str(payload.get("default_model") or DEFAULT_OPENAI_MODEL),
            providers=AppSettingsProviders(
                openai=remote_settings["openai"],
                claude=remote_settings["claude"],
                gemini=remote_settings["gemini"],
                local=local_settings,
            ),
            configured_providers=self._configured_providers(remote_settings, local_settings),
        )

    def _build_remote_provider_settings(
        self,
        payload: dict[str, Any],
        test_results: dict[str, dict[str, str]],
        provider: Literal["openai", "claude", "gemini"],
    ) -> RemoteProviderSettings:
        secret_value = payload.get(API_KEY_FIELDS[provider])
        return RemoteProviderSettings(
            api_key_configured=bool(self._normalize_secret(secret_value)),
            api_key_masked=self._mask_secret(secret_value),
            status=self._resolve_remote_status(payload, test_results, provider),
            last_test_message=test_results.get(provider, {}).get("message"),
            last_tested_at=self._parse_datetime(test_results.get(provider, {}).get("tested_at")),
        )

    def _configured_providers(
        self,
        remote_settings: Mapping[str, RemoteProviderSettings],
        local_settings: OllamaProviderSettings,
    ) -> list[ConfiguredProviderSummary]:
        providers: list[ConfiguredProviderSummary] = []
        for provider_name in REMOTE_PROVIDERS:
            provider_settings = remote_settings[provider_name]
            if provider_settings.api_key_configured:
                providers.append(
                    ConfiguredProviderSummary(
                        provider=provider_name,
                        label=PROVIDER_LABELS[provider_name],
                        status=provider_settings.status,
                        model=None,
                    )
                )
        if local_settings.base_url.strip():
            providers.append(
                ConfiguredProviderSummary(
                    provider="local",
                    label=PROVIDER_LABELS["local"],
                    status=local_settings.status,
                    model=local_settings.model,
                )
            )
        return providers

    def _resolve_remote_status(
        self,
        payload: dict[str, Any],
        test_results: dict[str, dict[str, str]],
        provider: Literal["openai", "claude", "gemini"],
    ) -> ProviderTestStatus:
        if not self._normalize_secret(payload.get(API_KEY_FIELDS[provider])):
            return "missing"
        status = test_results.get(provider, {}).get("status")
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
            "anthropic_api_key": None,
            "gemini_api_key": None,
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
        if value in {"openai", "claude", "gemini", "local"}:
            return value
        return "openai"

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None


settings_service = SettingsService()


__all__ = [
    "AppSettingsProviders",
    "AppSettingsResponse",
    "AppSettingsUpdate",
    "ConfiguredProviderSummary",
    "DEFAULT_CLAUDE_MODEL",
    "DEFAULT_GEMINI_MODEL",
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OPENAI_MODEL",
    "OllamaProviderSettings",
    "PROVIDER_LABELS",
    "ProviderTestRequest",
    "ProviderTestResponse",
    "ProviderTestStatus",
    "RemoteProviderSettings",
    "SettingsProvider",
    "SettingsService",
    "settings_service",
]
