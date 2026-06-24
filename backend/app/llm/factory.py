from __future__ import annotations

from pathlib import Path

from backend.app.llm.base import (
    BaseLLMProvider,
    LLMConfigurationError,
    normalize_provider_name,
)
from backend.app.llm.providers import (
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
)


def create_llm_provider(
    provider_name: str,
    *,
    default_model: str | None = None,
    ollama_base_url: str | None = None,
    secrets_path: Path | None = None,
) -> BaseLLMProvider:
    normalized = normalize_provider_name(provider_name)
    resolved_model = default_model
    resolved_ollama_base_url = ollama_base_url
    if normalized == "ollama" and (resolved_model is None or resolved_ollama_base_url is None):
        from backend.app.services.settings_service import settings_service

        settings = settings_service.get_settings()
        resolved_model = resolved_model or settings.providers.ollama.model
        resolved_ollama_base_url = (
            resolved_ollama_base_url or settings.providers.ollama.base_url
        )
    if normalized == "openai":
        return OpenAIProvider(default_model=default_model, secrets_path=secrets_path)
    if normalized == "claude":
        return AnthropicProvider(default_model=default_model, secrets_path=secrets_path)
    if normalized == "gemini":
        return GeminiProvider(default_model=default_model, secrets_path=secrets_path)
    if normalized == "ollama":
        return OllamaProvider(
            default_model=resolved_model,
            base_url=resolved_ollama_base_url or "http://localhost:11434",
        )
    raise LLMConfigurationError(
        f"Unsupported LLM provider: {provider_name}",
        retryable=False,
    )


__all__ = ["create_llm_provider", "normalize_provider_name"]
