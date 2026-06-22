from __future__ import annotations

import asyncio
import json
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


OpenAITransport = Callable[
    [str, Mapping[str, str], Mapping[str, Any], float],
    Mapping[str, Any] | Awaitable[Mapping[str, Any]],
]

# Cheap models for testing and experimentation
OPENAI_PRICING_USD_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


class OpenAIProvider(BaseLLMProvider):
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        default_model: str | None = None,
        secrets_path: Path | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        transport: OpenAITransport | None = None,
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
        self._pricing = pricing or OPENAI_PRICING_USD_PER_1M_TOKENS

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
            resolved_model = self.resolve_model(model)
            payload = self._build_payload(
                messages=messages,
                model=resolved_model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            response = await self._request(payload)
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
            resolved_model = self.resolve_model(model)
            payload = self._build_payload(
                messages=messages,
                model=resolved_model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                output_schema=output_schema,
            )
            response = await self._request(payload)
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
            return 0.0, [f"No OpenAI pricing configured for model {model}."]

        input_usd_per_1m, output_usd_per_1m = pricing
        cost = (
            (input_tokens / 1_000_000) * input_usd_per_1m
            + (output_tokens / 1_000_000) * output_usd_per_1m
        )
        return round(cost, 8), []

    def _api_key_value(self) -> str:
        api_key = self._api_key or get_provider_api_key(
            "openai",
            secrets_path=self._secrets_path,
            env_var="OPENAI_API_KEY",
        )
        if not api_key:
            raise LLMConfigurationError(
                (
                    "OpenAI API key is missing. Add it to "
                    "~/.openalpha/secrets.json as openai.api_key or set "
                    "OPENAI_API_KEY."
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
        payload: dict[str, Any] = {
            "model": model,
            "input": [
                {"role": message.role, "content": message.content}
                for message in self.normalize_messages(messages)
            ],
        }

        if temperature is not None:
            payload["temperature"] = temperature
        if max_output_tokens is not None:
            payload["max_output_tokens"] = max_output_tokens
        if output_schema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": output_schema.__name__,
                    "schema": self._build_strict_json_schema(output_schema),
                    "strict": True,
                }
            }

        return payload

    def _build_strict_json_schema(
        self,
        output_schema: type[BaseModel],
    ) -> dict[str, Any]:
        schema = output_schema.model_json_schema()
        return self._normalize_schema_node(schema)

    def _normalize_schema_node(self, node: Any) -> Any:
        if isinstance(node, list):
            return [self._normalize_schema_node(item) for item in node]
        if not isinstance(node, dict):
            return node

        normalized = {
            key: self._normalize_schema_node(value)
            for key, value in node.items()
            if key != "default"
        }

        properties = normalized.get("properties")
        if isinstance(properties, dict):
            normalized["required"] = list(properties.keys())
            normalized.setdefault("additionalProperties", False)

        return normalized

    async def _request(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key_value()}",
            "Content-Type": "application/json",
        }
        result = self._transport(
            f"{self.base_url}/responses",
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
            error_body = exc.read().decode("utf-8", errors="replace")
            error_message = self._error_message(error_body)
            retryable = exc.code in {408, 409, 429, 500, 502, 503, 504}
            if exc.code in {401, 403} or (
                exc.code == 429 and self._is_fatal_auth_or_quota_error(error_message)
            ):
                retryable = False
            raise LLMProviderError(
                f"OpenAI API returned HTTP {exc.code}: {error_message}",
                retryable=retryable,
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMProviderError(
                f"OpenAI API request failed: {exc.reason}",
                retryable=True,
            ) from exc

        try:
            data = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                f"OpenAI API returned invalid JSON: {exc}",
                retryable=True,
            ) from exc

        if not isinstance(data, dict):
            raise LLMProviderError(
                "OpenAI API returned an unexpected response shape.",
                retryable=True,
            )
        if "error" in data:
            raise LLMProviderError(
                f"OpenAI API error: {data['error']}",
                retryable=False,
            )
        return data

    def _extract_output_text(self, response: Mapping[str, Any]) -> str:
        output_text = response.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        output = response.get("output")
        if isinstance(output, list):
            text_chunks: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                content_items = item.get("content")
                if not isinstance(content_items, list):
                    continue
                for content_item in content_items:
                    if not isinstance(content_item, dict):
                        continue
                    text = content_item.get("text")
                    if isinstance(text, str):
                        text_chunks.append(text)

            combined = "".join(text_chunks).strip()
            if combined:
                return combined

        raise LLMResponseValidationError(
            "OpenAI response did not include output text.",
            retryable=True,
        )

    def _extract_usage(self, response: Mapping[str, Any]) -> TokenUsage:
        usage = response.get("usage")
        if not isinstance(usage, dict):
            return TokenUsage()

        input_tokens = self._coerce_token_count(usage.get("input_tokens"))
        output_tokens = self._coerce_token_count(usage.get("output_tokens"))
        total_tokens = self._coerce_token_count(usage.get("total_tokens"))
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens

        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    def _coerce_token_count(self, value: Any) -> int:
        if isinstance(value, int) and value >= 0:
            return value
        return 0

    def _error_message(self, error_body: str) -> str:
        try:
            data = json.loads(error_body)
        except json.JSONDecodeError:
            return error_body.strip() or "No error body returned."

        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()
        return error_body.strip() or "No error body returned."

    def _is_fatal_auth_or_quota_error(self, message: str) -> bool:
        normalized = message.lower()
        return any(
            marker in normalized
            for marker in (
                "quota exceeded",
                "exceeded your current quota",
                "api key is missing",
                "invalid api key",
                "unauthorized",
                "forbidden",
                "authentication failed",
                "invalid authentication",
            )
        )
