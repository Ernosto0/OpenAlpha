from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator
from sqlmodel import Session

from backend.app.db.models import Setting
from backend.app.db.session import engine
from backend.app.llm import LLMModelInfo
from backend.app.llm.base import normalize_provider_name
from backend.app.llm.providers.ollama_provider import OllamaProvider, OllamaTransport
from backend.app.orchestrator.schemas import OpenAlphaSchema, utc_now


CanonicalProvider = Literal["openai", "claude", "gemini", "ollama"]
ProviderInput = Literal["openai", "claude", "gemini", "ollama", "local"]
ProviderTestStatus = Literal["configured", "missing", "tested", "failed", "untested"]
ProviderKind = Literal["remote_api", "local_runtime"]
ProviderTestTransport = Callable[[str, Mapping[str, str], float], str]

SETTINGS_KEY = "app_settings"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-latest"
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"
DEFAULT_OLLAMA_MODEL = "llama3"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"

PROVIDER_LABELS: dict[CanonicalProvider, str] = {
    "openai": "OpenAI",
    "claude": "Claude",
    "gemini": "Gemini",
    "ollama": "Ollama",
}

REMOTE_PROVIDERS: tuple[CanonicalProvider, ...] = ("openai", "claude", "gemini")
API_KEY_FIELDS: dict[Literal["openai", "claude", "gemini"], str] = {
    "openai": "openai_api_key",
    "claude": "anthropic_api_key",
    "gemini": "gemini_api_key",
}


class ProviderCapabilityFlags(OpenAlphaSchema):
    health_check: bool
    list_models: bool
    requires_api_key: bool
    supports_structured_output: bool


class ProviderCatalogEntry(OpenAlphaSchema):
    id: CanonicalProvider
    label: str
    kind: ProviderKind
    capabilities: ProviderCapabilityFlags


class ConfiguredProviderSummary(OpenAlphaSchema):
    provider: CanonicalProvider
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
    ollama: OllamaProviderSettings


class AppSettingsResponse(OpenAlphaSchema):
    default_provider: CanonicalProvider = "openai"
    default_model: str = DEFAULT_OPENAI_MODEL
    providers: AppSettingsProviders
    configured_providers: list[ConfiguredProviderSummary] = Field(default_factory=list)


class AppSettingsUpdate(OpenAlphaSchema):
    default_provider: ProviderInput
    default_model: str = Field(min_length=1, max_length=120)
    openai_api_key: str | None = Field(default=None, max_length=500)
    anthropic_api_key: str | None = Field(default=None, max_length=500)
    gemini_api_key: str | None = Field(default=None, max_length=500)
    ollama_base_url: str = Field(min_length=1, max_length=300)
    ollama_model: str = Field(min_length=1, max_length=120)

    @field_validator("default_provider", mode="before")
    @classmethod
    def canonicalize_default_provider(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("default_provider must be a string")
        return normalize_provider_name(value)


class ProviderTestRequest(OpenAlphaSchema):
    provider: ProviderInput
    base_url: str | None = Field(default=None, max_length=300)
    model: str | None = Field(default=None, max_length=120)

    @field_validator("provider", mode="before")
    @classmethod
    def canonicalize_provider(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("provider must be a string")
        return normalize_provider_name(value)


class ProviderTestResponse(OpenAlphaSchema):
    provider: CanonicalProvider
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
        ollama_transport: OllamaTransport | None = None,
    ) -> None:
        self._session_factory = session_factory or (lambda: Session(engine))
        self._provider_test_transports: dict[str, ProviderTestTransport] = {
            "openai": openai_test_transport or self._default_test_transport,
            "claude": claude_test_transport or self._default_test_transport,
            "gemini": gemini_test_transport or self._default_test_transport,
        }
        self._ollama_transport = ollama_transport

    def get_settings(self) -> AppSettingsResponse:
        with self._session_factory() as session:
            payload = self._load_payload(session)
            return self._build_response(payload)

    def save_settings(self, update: AppSettingsUpdate) -> AppSettingsResponse:
        with self._session_factory() as session:
            payload = self._load_payload(session)
            payload["default_provider"] = normalize_provider_name(update.default_provider)
            payload["default_model"] = update.default_model.strip()
            if update.openai_api_key is not None:
                payload["openai_api_key"] = self._normalize_secret(update.openai_api_key)
            if update.anthropic_api_key is not None:
                payload["anthropic_api_key"] = self._normalize_secret(update.anthropic_api_key)
            if update.gemini_api_key is not None:
                payload["gemini_api_key"] = self._normalize_secret(update.gemini_api_key)
            payload["ollama_base_url"] = self._normalize_base_url(update.ollama_base_url)
            payload["ollama_model"] = update.ollama_model.strip()
            self._save_payload(session, payload)
            return self._build_response(payload)

    def list_provider_catalog(self) -> list[ProviderCatalogEntry]:
        return [
            ProviderCatalogEntry(
                id="openai",
                label="OpenAI",
                kind="remote_api",
                capabilities=ProviderCapabilityFlags(
                    health_check=True,
                    list_models=False,
                    requires_api_key=True,
                    supports_structured_output=True,
                ),
            ),
            ProviderCatalogEntry(
                id="claude",
                label="Claude",
                kind="remote_api",
                capabilities=ProviderCapabilityFlags(
                    health_check=True,
                    list_models=False,
                    requires_api_key=True,
                    supports_structured_output=True,
                ),
            ),
            ProviderCatalogEntry(
                id="gemini",
                label="Gemini",
                kind="remote_api",
                capabilities=ProviderCapabilityFlags(
                    health_check=True,
                    list_models=False,
                    requires_api_key=True,
                    supports_structured_output=True,
                ),
            ),
            ProviderCatalogEntry(
                id="ollama",
                label="Ollama",
                kind="local_runtime",
                capabilities=ProviderCapabilityFlags(
                    health_check=True,
                    list_models=True,
                    requires_api_key=False,
                    supports_structured_output=True,
                ),
            ),
        ]

    async def test_provider(self, request: ProviderTestRequest) -> ProviderTestResponse:
        with self._session_factory() as session:
            payload = self._load_payload(session)
            tested_at = utc_now()

            if request.provider == "ollama":
                response = await self._test_ollama_provider(
                    payload=payload,
                    tested_at=tested_at,
                    base_url=request.base_url,
                    model=request.model,
                )
            else:
                response = self._test_remote_provider(
                    request.provider,
                    payload,
                    tested_at,
                )

            test_results = payload.setdefault("provider_test_results", {})
            test_results[response.provider] = {
                "status": response.status,
                "message": response.message,
                "tested_at": response.tested_at.isoformat(),
            }
            self._save_payload(session, payload)
            return response

    async def list_ollama_models(self, *, base_url: str | None = None) -> list[LLMModelInfo]:
        provider = self._build_ollama_provider(base_url=base_url)
        return await provider.list_models()

    def get_ollama_runtime_config(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
    ) -> tuple[str, str]:
        settings = self.get_settings()
        return (
            self._normalize_base_url(base_url or settings.providers.ollama.base_url),
            (model or settings.providers.ollama.model).strip(),
        )

    def build_ollama_provider(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
    ) -> OllamaProvider:
        return self._build_ollama_provider(base_url=base_url, model=model)

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

    async def _test_ollama_provider(
        self,
        *,
        payload: dict[str, Any],
        tested_at: datetime,
        base_url: str | None,
        model: str | None,
    ) -> ProviderTestResponse:
        provider = self._build_ollama_provider(
            base_url=base_url or payload.get("ollama_base_url"),
            model=model or payload.get("ollama_model"),
        )
        health = await provider.health_check()
        if not health.available:
            return ProviderTestResponse(
                provider="ollama",
                success=False,
                status="failed",
                message=health.message,
                tested_at=tested_at,
            )

        models = await provider.list_models()
        if not models:
            return ProviderTestResponse(
                provider="ollama",
                success=True,
                status="tested",
                message=f"Ollama is connected at {provider.base_url}, but no models are installed.",
                tested_at=tested_at,
            )

        selected_model = (model or payload.get("ollama_model") or "").strip()
        if selected_model and not any(item.id == selected_model for item in models):
            return ProviderTestResponse(
                provider="ollama",
                success=False,
                status="failed",
                message=(
                    f"Ollama is connected at {provider.base_url}, but the selected model "
                    f"'{selected_model}' is unavailable."
                ),
                tested_at=tested_at,
            )

        return ProviderTestResponse(
            provider="ollama",
            success=True,
            status="tested",
            message=health.message,
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

    def _build_ollama_provider(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
    ) -> OllamaProvider:
        return OllamaProvider(
            base_url=self._normalize_base_url(base_url or DEFAULT_OLLAMA_BASE_URL),
            default_model=(model or DEFAULT_OLLAMA_MODEL).strip(),
            transport=self._ollama_transport,
        )

    def _load_payload(self, session: Session) -> dict[str, Any]:
        row = session.get(Setting, SETTINGS_KEY)
        if row is None or not isinstance(row.value_json, dict):
            return self._default_payload()

        payload = self._default_payload()
        payload.update(row.value_json)
        payload["default_provider"] = normalize_provider_name(
            str(row.value_json.get("default_provider") or payload["default_provider"])
        )
        payload["provider_test_results"] = self._normalize_test_results(
            row.value_json.get("provider_test_results")
        )
        return payload

    def _save_payload(self, session: Session, payload: dict[str, Any]) -> None:
        persisted_payload = {
            "default_provider": normalize_provider_name(
                str(payload.get("default_provider") or "openai")
            ),
            "default_model": str(payload.get("default_model") or DEFAULT_OPENAI_MODEL),
            "openai_api_key": payload.get("openai_api_key"),
            "anthropic_api_key": payload.get("anthropic_api_key"),
            "gemini_api_key": payload.get("gemini_api_key"),
            "ollama_base_url": self._normalize_base_url(
                str(payload.get("ollama_base_url") or DEFAULT_OLLAMA_BASE_URL)
            ),
            "ollama_model": str(payload.get("ollama_model") or DEFAULT_OLLAMA_MODEL).strip(),
            "provider_test_results": self._normalize_test_results(
                payload.get("provider_test_results")
            ),
        }
        row = session.get(Setting, SETTINGS_KEY)
        now = utc_now()
        if row is None:
            row = Setting(
                key=SETTINGS_KEY,
                value_json=persisted_payload,
                created_at=now,
                updated_at=now,
            )
        else:
            row.value_json = persisted_payload
            row.updated_at = now
        session.add(row)
        session.commit()

    def _build_response(self, payload: dict[str, Any]) -> AppSettingsResponse:
        test_results = self._normalize_test_results(payload.get("provider_test_results"))
        remote_settings = {
            provider: self._build_remote_provider_settings(payload, test_results, provider)
            for provider in REMOTE_PROVIDERS
        }
        ollama_settings = OllamaProviderSettings(
            base_url=self._normalize_base_url(
                str(payload.get("ollama_base_url") or DEFAULT_OLLAMA_BASE_URL)
            ),
            model=str(payload.get("ollama_model") or DEFAULT_OLLAMA_MODEL),
            status=self._resolve_ollama_status(payload, test_results),
            last_test_message=test_results.get("ollama", {}).get("message"),
            last_tested_at=self._parse_datetime(test_results.get("ollama", {}).get("tested_at")),
        )

        return AppSettingsResponse(
            default_provider=self._coerce_provider(payload.get("default_provider")),
            default_model=str(payload.get("default_model") or DEFAULT_OPENAI_MODEL),
            providers=AppSettingsProviders(
                openai=remote_settings["openai"],
                claude=remote_settings["claude"],
                gemini=remote_settings["gemini"],
                ollama=ollama_settings,
            ),
            configured_providers=self._configured_providers(remote_settings, ollama_settings),
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
        ollama_settings: OllamaProviderSettings,
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
        if ollama_settings.base_url.strip():
            providers.append(
                ConfiguredProviderSummary(
                    provider="ollama",
                    label=PROVIDER_LABELS["ollama"],
                    status=ollama_settings.status,
                    model=ollama_settings.model,
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

    def _resolve_ollama_status(
        self,
        payload: dict[str, Any],
        test_results: dict[str, dict[str, str]],
    ) -> ProviderTestStatus:
        if not str(payload.get("ollama_base_url") or "").strip():
            return "missing"
        status = test_results.get("ollama", {}).get("status")
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
            canonical_name = normalize_provider_name(provider_name)
            entry: dict[str, str] = {}
            for key in ("status", "message", "tested_at"):
                item = result.get(key)
                if isinstance(item, str) and item.strip():
                    entry[key] = item.strip()
            normalized[canonical_name] = entry
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

    def _coerce_provider(self, value: Any) -> CanonicalProvider:
        normalized = normalize_provider_name(str(value or "openai"))
        if normalized in {"openai", "claude", "gemini", "ollama"}:
            return normalized
        return "openai"

    def _normalize_base_url(self, value: str) -> str:
        return value.strip().rstrip("/")

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
    "ProviderCatalogEntry",
    "ProviderTestRequest",
    "ProviderTestResponse",
    "ProviderTestStatus",
    "RemoteProviderSettings",
    "SettingsService",
    "settings_service",
]
