from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from backend.app.core.secrets import get_provider_api_key
from backend.app.llm.base import (
    BaseLLMProvider,
    LLMConfigurationError,
    LLMMessage,
    LLMProviderError,
    LLMResponseValidationError,
    LLMResult,
    TokenUsage,
    TModel,
)


AnthropicTransport = Callable[
    [str, Mapping[str, str], Mapping[str, Any], float],
    Mapping[str, Any] | Awaitable[Mapping[str, Any]],
]

ANTHROPIC_PRICING_USD_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    "claude-3-5-sonnet-latest": (3.00, 15.00),
    "claude-3-5-haiku-latest": (0.80, 4.00),
    "claude-3-7-sonnet-latest": (3.00, 15.00),
}

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    provider_name = "claude"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        default_model: str | None = None,
        secrets_path: Path | None = None,
        base_url: str = "https://api.anthropic.com/v1",
        timeout_seconds: float = 60,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        transport: AnthropicTransport | None = None,
        pricing: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        super().__init__(
            default_model=default_model,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
        )
        self._api_key = api_key
        self._secrets_path = secrets_path
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._transport = transport or self._post_json
        self._pricing = pricing or ANTHROPIC_PRICING_USD_PER_1M_TOKENS

    async def generate(
        self,
        *,
        messages: Sequence[LLMMessage | Mapping[str, str]],
        model: str | None = None,
        agent_name: str = "unknown",
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResult:
        async def operation() -> LLMResult:
            started = self.start_timer()
            resolved_model = self.resolve_model(model)
            payload = self._build_payload(
                messages=messages,
                model=resolved_model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            response = await self._request(payload)
            self._raise_for_incomplete_response(response)
            raw_content = self._extract_output_text(response)
            usage = self._extract_usage(response)
            cost, warnings = self.calculate_cost(
                model=resolved_model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )

            return LLMResult(
                provider=self.provider_name,
                model=resolved_model,
                agent_name=agent_name,
                content=raw_content,
                raw_content=raw_content,
                raw_response=dict(response),
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                estimated_cost_usd=cost,
                cost_type="api",
                duration_ms=self.elapsed_ms(started),
                warnings=warnings,
            )

        return await self._run_with_retries(operation)

    async def generate_json(
        self,
        *,
        messages: Sequence[LLMMessage | Mapping[str, str]],
        output_schema: type[TModel],
        model: str | None = None,
        agent_name: str = "unknown",
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResult:
        async def operation() -> LLMResult:
            started = self.start_timer()
            resolved_model = self.resolve_model(model)
            payload = self._build_payload(
                messages=messages,
                model=resolved_model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                output_schema=output_schema,
            )
            response = await self._request(payload)
            self._raise_for_incomplete_response(response)
            raw_content = self._extract_output_text(response)
            content = self.validate_json_content(raw_content, output_schema)
            usage = self._extract_usage(response)
            cost, warnings = self.calculate_cost(
                model=resolved_model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )

            return LLMResult(
                provider=self.provider_name,
                model=resolved_model,
                agent_name=agent_name,
                content=content,
                raw_content=raw_content,
                raw_response=dict(response),
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                estimated_cost_usd=cost,
                cost_type="api",
                duration_ms=self.elapsed_ms(started),
                warnings=warnings,
            )

        return await self._run_with_retries(operation)

    def calculate_cost(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> tuple[float, list[str]]:
        pricing = self._pricing.get(model)
        if pricing is None:
            return 0.0, [f"No Claude pricing configured for model {model}."]

        input_usd_per_1m, output_usd_per_1m = pricing
        cost = (
            (input_tokens / 1_000_000) * input_usd_per_1m
            + (output_tokens / 1_000_000) * output_usd_per_1m
        )
        return round(cost, 8), []

    def _api_key_value(self) -> str:
        api_key = self._api_key or get_provider_api_key(
            "claude",
            secrets_path=self._secrets_path,
            env_var="ANTHROPIC_API_KEY",
        )
        if not api_key:
            raise LLMConfigurationError(
                (
                    "Claude API key is missing. Add it to "
                    "~/.openalpha/secrets.json as claude.api_key or set "
                    "ANTHROPIC_API_KEY."
                ),
                retryable=False,
            )
        return api_key

    def _build_payload(
        self,
        *,
        messages: Sequence[LLMMessage | Mapping[str, str]],
        model: str,
        temperature: float | None,
        max_output_tokens: int | None,
        output_schema: type[BaseModel] | None = None,
    ) -> dict[str, Any]:
        normalized_messages = self.normalize_messages(messages)
        system_messages = [
            message.content for message in normalized_messages if message.role == "system"
        ]
        conversation_messages = [
            {
                "role": "assistant" if message.role == "assistant" else "user",
                "content": [{"type": "text", "text": message.content}],
            }
            for message in normalized_messages
            if message.role != "system"
        ]
        if output_schema is not None:
            conversation_messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self._json_instruction(output_schema),
                        }
                    ],
                }
            )

        payload: dict[str, Any] = {
            "model": model,
            "messages": conversation_messages,
            "max_tokens": max_output_tokens or 4096,
        }
        if system_messages:
            payload["system"] = "\n\n".join(system_messages)
        if temperature is not None:
            payload["temperature"] = temperature
        return payload

    def _json_instruction(self, output_schema: type[BaseModel]) -> str:
        schema = json.dumps(output_schema.model_json_schema(), sort_keys=True)
        return (
            "Return valid JSON only. Do not include markdown, prose, or code fences. "
            f"The JSON must satisfy this schema: {schema}"
        )

    async def _request(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        headers = {
            "x-api-key": self._api_key_value(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        result = self._transport(
            f"{self.base_url}/messages",
            headers,
            payload,
            self.timeout_seconds,
        )
        if asyncio.iscoroutine(result):
            result = await result
        return result

    async def _post_json(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(
            self._post_json_sync,
            url,
            headers,
            payload,
            timeout_seconds,
        )

    def _post_json_sync(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers=dict(headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_message = self._read_http_error(exc)
            retryable = exc.code in {408, 409, 429, 500, 502, 503, 504}
            if exc.code in {401, 403} or (
                exc.code == 429 and self._is_fatal_auth_or_quota_error(error_message)
            ):
                retryable = False
            raise LLMProviderError(
                f"Claude API returned HTTP {exc.code}: {error_message}",
                retryable=retryable,
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMProviderError(
                f"Claude API request failed: {exc.reason}",
                retryable=True,
            ) from exc

        try:
            data = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                f"Claude API returned invalid JSON: {exc}",
                retryable=True,
            ) from exc

        if not isinstance(data, dict):
            raise LLMProviderError(
                "Claude API returned an unexpected response shape.",
                retryable=True,
            )
        return data

    def _read_http_error(self, exc: urllib.error.HTTPError) -> str:
        error_body = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(error_body)
        except json.JSONDecodeError:
            return error_body.strip() or f"HTTP {exc.code}"

        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()
            message = data.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        return error_body.strip() or f"HTTP {exc.code}"

    def _extract_output_text(self, response: Mapping[str, Any]) -> str:
        content = response.get("content")
        if not isinstance(content, list):
            raise LLMResponseValidationError(
                "Claude response did not include content.",
                retryable=True,
            )

        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                text_parts.append(text)
        combined = "".join(text_parts).strip()
        if not combined:
            raise LLMResponseValidationError(
                "Claude response did not include text content.",
                retryable=True,
            )
        return combined

    def _raise_for_incomplete_response(self, response: Mapping[str, Any]) -> None:
        stop_reason = response.get("stop_reason")
        if stop_reason != "max_tokens":
            return
        raise LLMProviderError(
            "Claude response was incomplete because max_tokens was reached.",
            retryable=False,
        )

    def _extract_usage(self, response: Mapping[str, Any]) -> TokenUsage:
        usage = response.get("usage")
        if not isinstance(usage, dict):
            return TokenUsage()

        input_tokens = self._coerce_token_count(usage.get("input_tokens"))
        output_tokens = self._coerce_token_count(usage.get("output_tokens"))
        total_tokens = input_tokens + output_tokens
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    def _coerce_token_count(self, value: Any) -> int:
        return value if isinstance(value, int) and value >= 0 else 0

    def _is_fatal_auth_or_quota_error(self, message: str) -> bool:
        normalized = message.lower()
        return any(
            marker in normalized
            for marker in (
                "quota exceeded",
                "credit balance is too low",
                "api key is missing",
                "invalid api key",
                "unauthorized",
                "forbidden",
                "authentication",
            )
        )


__all__ = ["ANTHROPIC_PRICING_USD_PER_1M_TOKENS", "AnthropicProvider"]
