from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.secrets import get_provider_api_key
from backend.app.llm import LLMConfigurationError, LLMProviderError
from backend.app.llm.providers import OpenAIProvider


class ExampleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)


def write_secrets(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def response_with_text(text: str) -> dict[str, Any]:
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
        return response_with_text('{"rating": "ok", "score": 0.8}')

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
        return response_with_text('{"rating": "ok", "score": 0.7}')

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


def test_openai_generate_json_reports_validation_errors() -> None:
    provider = OpenAIProvider(
        api_key="test-key",
        default_model="gpt-4.1-mini",
        retry_backoff_seconds=0,
        max_retries=0,
        transport=lambda *_args: response_with_text('{"rating": "", "score": 2}'),
    )

    with pytest.raises(LLMProviderError, match="ExampleOutput validation"):
        asyncio.run(
            provider.generate_json(
                messages=[{"role": "user", "content": "Analyze TSLA."}],
                output_schema=ExampleOutput,
            )
        )


def test_openai_requires_api_key_before_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    provider = OpenAIProvider(
        default_model="gpt-4.1-mini",
        secrets_path=Path("missing-secrets.json"),
        transport=lambda *_args: response_with_text("{}"),
    )

    with pytest.raises(LLMConfigurationError, match="OpenAI API key is missing"):
        asyncio.run(
            provider.generate(
                messages=[{"role": "user", "content": "Hello"}],
            )
        )
