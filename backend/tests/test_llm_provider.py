from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.secrets import get_provider_api_key
from backend.app.llm import (
    LLMConfigurationError,
    LLMProviderError,
    create_llm_provider,
    should_stop_analysis_for_llm_error,
)
from backend.app.llm.providers import (
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
)


class ExampleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)


class ExampleNestedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    note: str | None = None


class ExampleOptionalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    note: str | None = None
    items: list[ExampleNestedItem] = Field(default_factory=list)


def write_secrets(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def openai_response_with_text(text: str) -> dict[str, Any]:
    return {
        "output": [
            {
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                    }
                ]
            }
        ],
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 500,
            "total_tokens": 1500,
        },
    }


def anthropic_response_with_text(text: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "usage": {
            "input_tokens": 800,
            "output_tokens": 200,
        },
        "stop_reason": "end_turn",
    }


def gemini_response_with_text(text: str) -> dict[str, Any]:
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": text}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 900,
            "candidatesTokenCount": 300,
            "totalTokenCount": 1200,
        },
    }


def test_get_provider_api_key_reads_local_provider_secret(tmp_path: Path) -> None:
    secrets_path = write_secrets(
        tmp_path / "secrets.json",
        {"openai": {"api_key": "local-secret"}},
    )

    assert get_provider_api_key("openai", secrets_path=secrets_path) == "local-secret"


def test_openai_generate_json_sends_schema_and_returns_usage(
    tmp_path: Path,
) -> None:
    secrets_path = write_secrets(
        tmp_path / "secrets.json",
        {"openai": {"api_key": "local-secret"}},
    )
    calls: list[dict[str, Any]] = []

    def transport(
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return openai_response_with_text('{"rating": "ok", "score": 0.8}')

    provider = OpenAIProvider(
        default_model="gpt-4.1-mini",
        secrets_path=secrets_path,
        transport=transport,
    )

    result = asyncio.run(
        provider.generate_json(
            messages=[{"role": "user", "content": "Analyze AAPL."}],
            output_schema=ExampleOutput,
            agent_name="technical_agent",
        )
    )

    assert isinstance(result.content, ExampleOutput)
    assert result.content.rating == "ok"
    assert result.input_tokens == 1000
    assert result.output_tokens == 500
    assert result.total_tokens == 1500
    assert result.estimated_cost_usd == pytest.approx(0.0012)
    assert calls[0]["url"] == "https://api.openai.com/v1/responses"
    assert calls[0]["headers"]["Authorization"] == "Bearer local-secret"
    assert calls[0]["payload"]["model"] == "gpt-4.1-mini"
    assert calls[0]["payload"]["text"]["format"]["type"] == "json_schema"
    assert calls[0]["payload"]["text"]["format"]["strict"] is True
    assert calls[0]["payload"]["text"]["format"]["schema"]["title"] == "ExampleOutput"


def test_openai_generate_json_retries_retryable_errors() -> None:
    call_count = 0

    def transport(
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise LLMProviderError("rate limited", retryable=True)
        return openai_response_with_text('{"rating": "ok", "score": 0.7}')

    provider = OpenAIProvider(
        api_key="test-key",
        default_model="gpt-4.1-mini",
        retry_backoff_seconds=0,
        transport=transport,
    )

    result = asyncio.run(
        provider.generate_json(
            messages=[{"role": "user", "content": "Analyze MSFT."}],
            output_schema=ExampleOutput,
        )
    )

    assert call_count == 2
    assert result.content.score == 0.7


def test_openai_generate_json_normalizes_optional_fields_for_strict_schema() -> None:
    calls: list[dict[str, Any]] = []

    def transport(
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        calls.append(payload)
        return openai_response_with_text(
            '{"rating": "ok", "score": 0.7, "note": null, "items": []}'
        )

    provider = OpenAIProvider(
        api_key="test-key",
        default_model="gpt-4.1-mini",
        transport=transport,
    )

    asyncio.run(
        provider.generate_json(
            messages=[{"role": "user", "content": "Analyze AMZN."}],
            output_schema=ExampleOptionalOutput,
        )
    )

    schema = calls[0]["text"]["format"]["schema"]
    assert schema["required"] == ["rating", "score", "note", "items"]
    assert "default" not in schema["properties"]["note"]
    nested = schema["$defs"]["ExampleNestedItem"]
    assert nested["required"] == ["title", "note"]
    assert "default" not in nested["properties"]["note"]


def test_openai_generate_json_reports_validation_errors() -> None:
    provider = OpenAIProvider(
        api_key="test-key",
        default_model="gpt-4.1-mini",
        retry_backoff_seconds=0,
        max_retries=0,
        transport=lambda *_args: openai_response_with_text('{"rating": "", "score": 2}'),
    )

    with pytest.raises(LLMProviderError, match="ExampleOutput validation"):
        asyncio.run(
            provider.generate_json(
                messages=[{"role": "user", "content": "Analyze TSLA."}],
                output_schema=ExampleOutput,
            )
        )


def test_openai_generate_json_ignores_null_top_level_error() -> None:
    provider = OpenAIProvider(
        api_key="test-key",
        default_model="gpt-4.1-mini",
        transport=lambda *_args: {
            "id": "resp_123",
            "status": "completed",
            "error": None,
            **openai_response_with_text('{"rating": "ok", "score": 0.6}'),
        },
    )

    result = asyncio.run(
        provider.generate_json(
            messages=[{"role": "user", "content": "Analyze META."}],
            output_schema=ExampleOutput,
        )
    )

    assert result.content.rating == "ok"
    assert result.content.score == pytest.approx(0.6)


def test_openai_generate_json_reports_incomplete_response_reason() -> None:
    provider = OpenAIProvider(
        api_key="test-key",
        default_model="gpt-4.1-mini",
        max_retries=0,
        transport=lambda *_args: {
            "id": "resp_456",
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            **openai_response_with_text('{"rating":"ok"'),
        },
    )

    with pytest.raises(
        LLMProviderError,
        match="max_output_tokens was reached",
    ):
        asyncio.run(
            provider.generate_json(
                messages=[{"role": "user", "content": "Analyze NFLX."}],
                output_schema=ExampleOutput,
            )
        )


def test_openai_requires_api_key_before_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    provider = OpenAIProvider(
        default_model="gpt-4.1-mini",
        secrets_path=Path("missing-secrets.json"),
        transport=lambda *_args: openai_response_with_text("{}"),
    )

    with pytest.raises(LLMConfigurationError, match="OpenAI API key is missing"):
        asyncio.run(
            provider.generate(
                messages=[{"role": "user", "content": "Hello"}],
            )
        )


@pytest.mark.parametrize(
    ("provider_class", "api_key", "default_model", "response_factory", "expected_cost"),
    [
        (
            AnthropicProvider,
            "anthropic-test-key",
            "claude-3-5-sonnet-latest",
            anthropic_response_with_text,
            0.0054,
        ),
        (
            GeminiProvider,
            "gemini-test-key",
            "gemini-2.5-pro",
            gemini_response_with_text,
            0.004125,
        ),
    ],
)
def test_non_openai_generate_json_success_paths(
    provider_class: type[AnthropicProvider] | type[GeminiProvider],
    api_key: str,
    default_model: str,
    response_factory: Any,
    expected_cost: float,
) -> None:
    calls: list[dict[str, Any]] = []

    def transport(
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return response_factory('{"rating": "ok", "score": 0.75}')

    provider = provider_class(
        api_key=api_key,
        default_model=default_model,
        retry_backoff_seconds=0,
        transport=transport,
    )

    result = asyncio.run(
        provider.generate_json(
            messages=[{"role": "system", "content": "You are structured."}, {"role": "user", "content": "Analyze AAPL."}],
            output_schema=ExampleOutput,
            agent_name="technical_agent",
        )
    )

    assert isinstance(result.content, ExampleOutput)
    assert result.content.score == pytest.approx(0.75)
    assert result.estimated_cost_usd == pytest.approx(expected_cost)
    assert calls[0]["payload"]


def test_anthropic_generate_json_retries_retryable_errors() -> None:
    call_count = 0

    def transport(*_args: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise LLMProviderError("temporary network issue", retryable=True)
        return anthropic_response_with_text('{"rating": "ok", "score": 0.61}')

    provider = AnthropicProvider(
        api_key="anthropic-test-key",
        default_model="claude-3-5-sonnet-latest",
        retry_backoff_seconds=0,
        transport=transport,
    )

    result = asyncio.run(
        provider.generate_json(
            messages=[{"role": "user", "content": "Analyze AMD."}],
            output_schema=ExampleOutput,
        )
    )

    assert call_count == 2
    assert result.content.score == pytest.approx(0.61)


@pytest.mark.parametrize(
    ("provider_class", "default_model", "expected_message"),
    [
        (AnthropicProvider, "claude-3-5-sonnet-latest", "Claude API key is missing"),
        (GeminiProvider, "gemini-2.5-pro", "Gemini API key is missing"),
    ],
)
def test_non_openai_requires_api_key_before_request(
    provider_class: type[AnthropicProvider] | type[GeminiProvider],
    default_model: str,
    expected_message: str,
) -> None:
    provider = provider_class(
        default_model=default_model,
        secrets_path=Path("missing-secrets.json"),
        transport=lambda *_args: {},
    )

    with pytest.raises(LLMConfigurationError, match=expected_message):
        asyncio.run(
            provider.generate(
                messages=[{"role": "user", "content": "Hello"}],
            )
        )


@pytest.mark.parametrize(
    ("provider_class", "api_key", "default_model", "response_factory"),
    [
        (
            AnthropicProvider,
            "anthropic-test-key",
            "claude-3-5-sonnet-latest",
            anthropic_response_with_text,
        ),
        (
            GeminiProvider,
            "gemini-test-key",
            "gemini-2.5-pro",
            gemini_response_with_text,
        ),
    ],
)
def test_non_openai_generate_json_reports_validation_errors(
    provider_class: type[AnthropicProvider] | type[GeminiProvider],
    api_key: str,
    default_model: str,
    response_factory: Any,
) -> None:
    provider = provider_class(
        api_key=api_key,
        default_model=default_model,
        retry_backoff_seconds=0,
        max_retries=0,
        transport=lambda *_args: response_factory('{"rating": "", "score": 2}'),
    )

    with pytest.raises(LLMProviderError, match="ExampleOutput validation"):
        asyncio.run(
            provider.generate_json(
                messages=[{"role": "user", "content": "Analyze GOOG."}],
                output_schema=ExampleOutput,
            )
        )


def test_gemini_generate_json_handles_invalid_json_and_unknown_pricing() -> None:
    provider = GeminiProvider(
        api_key="gemini-test-key",
        default_model="gemini-unknown",
        retry_backoff_seconds=0,
        max_retries=0,
        transport=lambda *_args: gemini_response_with_text("not-json"),
    )

    with pytest.raises(LLMProviderError, match="Invalid JSON|not valid JSON"):
        asyncio.run(
            provider.generate_json(
                messages=[{"role": "user", "content": "Analyze GOOG."}],
                output_schema=ExampleOutput,
            )
        )

    text_provider = GeminiProvider(
        api_key="gemini-test-key",
        default_model="gemini-unknown",
        transport=lambda *_args: gemini_response_with_text("plain text response"),
    )
    text_result = asyncio.run(
        text_provider.generate(
            messages=[{"role": "user", "content": "Say hello."}],
        )
    )
    assert text_result.estimated_cost_usd == 0
    assert text_result.warnings == ["No Gemini pricing configured for model gemini-unknown."]


def test_quota_and_auth_errors_stop_analysis() -> None:
    assert should_stop_analysis_for_llm_error(
        LLMProviderError("OpenAI API returned HTTP 429: quota exceeded", status_code=429)
    )
    assert should_stop_analysis_for_llm_error(
        LLMProviderError("OpenAI API returned HTTP 401: unauthorized", status_code=401)
    )
    assert not should_stop_analysis_for_llm_error(
        LLMProviderError("OpenAI API returned HTTP 400: invalid response format")
    )


def test_create_llm_provider_accepts_ollama_alias() -> None:
    provider = create_llm_provider(
        "local",
        default_model="llama3.1",
        ollama_base_url="http://localhost:11434",
    )

    assert isinstance(provider, OllamaProvider)
    assert provider.provider_name == "ollama"


def test_ollama_health_and_model_listing() -> None:
    async def transport(
        method: str,
        url: str,
        _headers: dict[str, str],
        _payload: dict[str, Any] | None,
        _timeout_seconds: float,
    ) -> dict[str, Any]:
        assert method == "GET"
        assert url == "http://localhost:11434/api/tags"
        return {
            "models": [
                {
                    "name": "llama3.1",
                    "model": "llama3.1",
                    "size": 1024,
                    "details": {
                        "family": "llama",
                        "parameter_size": "8B",
                        "quantization_level": "Q4_K_M",
                    },
                }
            ]
        }

    provider = OllamaProvider(
        base_url="http://localhost:11434",
        default_model="llama3.1",
        transport=transport,
    )
    health = asyncio.run(provider.health_check())
    models = asyncio.run(provider.list_models())

    assert health.available is True
    assert models[0].id == "llama3.1"
    assert models[0].family == "llama"


def test_ollama_generate_and_generate_json() -> None:
    calls: list[dict[str, Any]] = []

    async def transport(
        method: str,
        url: str,
        _headers: dict[str, str],
        payload: dict[str, Any] | None,
        _timeout_seconds: float,
    ) -> dict[str, Any]:
        calls.append({"method": method, "url": url, "payload": payload})
        if payload and payload.get("format"):
            return {
                "message": {"content": '{"rating": "ok", "score": 0.85}'},
                "prompt_eval_count": 25,
                "eval_count": 10,
            }
        return {
            "message": {"content": "plain text"},
            "prompt_eval_count": 12,
            "eval_count": 5,
        }

    provider = OllamaProvider(
        base_url="http://localhost:11434",
        default_model="llama3.1",
        retry_backoff_seconds=0,
        transport=transport,
    )
    text_result = asyncio.run(
        provider.generate(messages=[{"role": "user", "content": "hello"}])
    )
    json_result = asyncio.run(
        provider.generate_json(
            messages=[{"role": "user", "content": "analyze"}],
            output_schema=ExampleOutput,
        )
    )

    assert text_result.content == "plain text"
    assert text_result.cost_type == "local"
    assert text_result.estimated_cost_usd == 0
    assert isinstance(json_result.content, ExampleOutput)
    assert json_result.content.score == pytest.approx(0.85)
    assert json_result.cost_type == "local"
    assert calls[1]["payload"]["format"]["type"] == "json_schema"


def test_ollama_generate_json_returns_warnings_after_retry_failure() -> None:
    call_count = 0

    async def transport(*_args: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return {
            "message": {"content": '{"rating": "", "score": 2}'},
            "prompt_eval_count": 25,
            "eval_count": 10,
        }

    provider = OllamaProvider(
        base_url="http://localhost:11434",
        default_model="llama3.1",
        retry_backoff_seconds=0,
        transport=transport,
    )

    result = asyncio.run(
        provider.generate_json(
            messages=[{"role": "user", "content": "analyze"}],
            output_schema=ExampleOutput,
        )
    )

    assert call_count == 2
    assert result.content is None
    assert result.error_message is not None
    assert result.warnings
    assert result.parsing_errors
