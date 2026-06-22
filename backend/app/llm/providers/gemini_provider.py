from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
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


GeminiTransport = Callable[
    [str, Mapping[str, str], Mapping[str, Any], float],
    Mapping[str, Any] | Awaitable[Mapping[str, Any]],
]

GEMINI_PRICING_USD_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
}


class GeminiProvider(BaseLLMProvider):
    provider_name = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        default_model: str | None = None,
        secrets_path: Path | None = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 60,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        transport: GeminiTransport | None = None,
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
        self._pricing = pricing or GEMINI_PRICING_USD_PER_1M_TOKENS

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
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            response = await self._request(resolved_model, payload)
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
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                output_schema=output_schema,
            )
            response = await self._request(resolved_model, payload)
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
            return 0.0, [f"No Gemini pricing configured for model {model}."]

        input_usd_per_1m, output_usd_per_1m = pricing
        cost = (
            (input_tokens / 1_000_000) * input_usd_per_1m
            + (output_tokens / 1_000_000) * output_usd_per_1m
        )
        return round(cost, 8), []

    def _api_key_value(self) -> str:
        api_key = self._api_key or get_provider_api_key(
            "gemini",
            secrets_path=self._secrets_path,
            env_var="GEMINI_API_KEY",
        )
        if not api_key:
            raise LLMConfigurationError(
                (
                    "Gemini API key is missing. Add it to "
                    "~/.openalpha/secrets.json as gemini.api_key or set "
                    "GEMINI_API_KEY."
                ),
                retryable=False,
            )
        return api_key

    def _build_payload(
        self,
        *,
        messages: Sequence[LLMMessage | Mapping[str, str]],
        temperature: float | None,
        max_output_tokens: int | None,
        output_schema: type[BaseModel] | None = None,
    ) -> dict[str, Any]:
        normalized_messages = self.normalize_messages(messages)
        system_messages = [
            message.content for message in normalized_messages if message.role == "system"
        ]
        contents = [
            {
                "role": "model" if message.role == "assistant" else "user",
                "parts": [{"text": message.content}],
            }
            for message in normalized_messages
            if message.role != "system"
        ]

        payload: dict[str, Any] = {"contents": contents}
        if system_messages:
            payload["system_instruction"] = {
                "parts": [{"text": "\n\n".join(system_messages)}]
            }

        generation_config: dict[str, Any] = {}
        if temperature is not None:
            generation_config["temperature"] = temperature
        if max_output_tokens is not None:
            generation_config["maxOutputTokens"] = max_output_tokens
        if output_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = output_schema.model_json_schema()
        if generation_config:
            payload["generationConfig"] = generation_config
        return payload

    async def _request(
        self,
        model: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        encoded_key = urllib.parse.quote(self._api_key_value(), safe="")
        url = f"{self.base_url}/models/{model}:generateContent?key={encoded_key}"
        result = self._transport(url, {"Content-Type": "application/json"}, payload, self.timeout_seconds)
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
            if exc.code in {400, 401, 403} and self._is_fatal_auth_error(error_message):
                retryable = False
            raise LLMProviderError(
                f"Gemini API returned HTTP {exc.code}: {error_message}",
                retryable=retryable,
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMProviderError(
                f"Gemini API request failed: {exc.reason}",
                retryable=True,
            ) from exc

        try:
            data = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                f"Gemini API returned invalid JSON: {exc}",
                retryable=True,
            ) from exc
        if not isinstance(data, dict):
            raise LLMProviderError(
                "Gemini API returned an unexpected response shape.",
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
        return error_body.strip() or f"HTTP {exc.code}"

    def _extract_output_text(self, response: Mapping[str, Any]) -> str:
        candidates = response.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise LLMResponseValidationError(
                "Gemini response did not include candidates.",
                retryable=True,
            )

        first = candidates[0]
        if not isinstance(first, dict):
            raise LLMResponseValidationError(
                "Gemini response candidate was invalid.",
                retryable=True,
            )
        content = first.get("content")
        if not isinstance(content, dict):
            raise LLMResponseValidationError(
                "Gemini response did not include content.",
                retryable=True,
            )
        parts = content.get("parts")
        if not isinstance(parts, list):
            raise LLMResponseValidationError(
                "Gemini response did not include parts.",
                retryable=True,
            )

        text_parts: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                text_parts.append(text)
        combined = "".join(text_parts).strip()
        if not combined:
            raise LLMResponseValidationError(
                "Gemini response did not include text output.",
                retryable=True,
            )
        return combined

    def _raise_for_incomplete_response(self, response: Mapping[str, Any]) -> None:
        candidates = response.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return
        first = candidates[0]
        if not isinstance(first, dict):
            return
        if first.get("finishReason") == "MAX_TOKENS":
            raise LLMProviderError(
                "Gemini response was incomplete because maxOutputTokens was reached.",
                retryable=False,
            )

    def _extract_usage(self, response: Mapping[str, Any]) -> TokenUsage:
        usage = response.get("usageMetadata")
        if not isinstance(usage, dict):
            return TokenUsage()

        input_tokens = self._coerce_token_count(usage.get("promptTokenCount"))
        output_tokens = self._coerce_token_count(usage.get("candidatesTokenCount"))
        total_tokens = self._coerce_token_count(usage.get("totalTokenCount"))
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    def _coerce_token_count(self, value: Any) -> int:
        return value if isinstance(value, int) and value >= 0 else 0

    def _is_fatal_auth_error(self, message: str) -> bool:
        normalized = message.lower()
        return any(
            marker in normalized
            for marker in (
                "api key not valid",
                "permission denied",
                "authentication",
                "unauthorized",
                "forbidden",
                "quota",
            )
        )


__all__ = ["GEMINI_PRICING_USD_PER_1M_TOKENS", "GeminiProvider"]
