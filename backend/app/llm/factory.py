from __future__ import annotations

from pathlib import Path

from backend.app.llm import BaseLLMProvider, LLMConfigurationError
from backend.app.llm.providers import AnthropicProvider, GeminiProvider, OpenAIProvider


def create_llm_provider(
    provider_name: str,
    *,
    default_model: str | None = None,
    secrets_path: Path | None = None,
) -> BaseLLMProvider:
    normalized = provider_name.strip().lower()
    if normalized == "openai":
        return OpenAIProvider(default_model=default_model, secrets_path=secrets_path)
    if normalized == "claude":
        return AnthropicProvider(default_model=default_model, secrets_path=secrets_path)
    if normalized == "gemini":
        return GeminiProvider(default_model=default_model, secrets_path=secrets_path)
    if normalized == "local":
        raise LLMConfigurationError(
            "Local Ollama runtime is not implemented for active LLM agents yet.",
            retryable=False,
        )
    raise LLMConfigurationError(
        f"Unsupported LLM provider: {provider_name}",
        retryable=False,
    )


__all__ = ["create_llm_provider"]
