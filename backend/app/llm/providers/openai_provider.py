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

logger = logging.getLogger(__name__)


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
        logger.info(
            "OpenAI request started",
            extra=self._log_extra(payload),
        )
        headers = {
            "Authorization": f"Bearer {self._api_key_value()}",
            "Content-Type": "application/json",
        }
        try:
            result = self._transport(
                f"{self.base_url}/responses",
                headers,
                payload,
                self.timeout_seconds,
            )
            if asyncio.iscoroutine(result):
                result = await result
        except TimeoutError as exc:
            logger.warning(
                "OpenAI request timed out",
                extra=self._log_extra(payload, error_message=str(exc)),
            )
            raise LLMProviderError(
                f"OpenAI API request timed out after {self.timeout_seconds} seconds.",
                retryable=True,
            ) from exc
        logger.info(
            "OpenAI request completed",
            extra=self._log_extra(payload, response=result),
        )
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
        except TimeoutError as exc:
            logger.warning(
                "OpenAI request timed out",
                extra=self._log_extra(
                    payload,
                    error_message=str(exc) or f"timeout after {timeout_seconds} seconds",
                ),
            )
            raise LLMProviderError(
                f"OpenAI API request timed out after {timeout_seconds} seconds.",
                retryable=True,
            ) from exc
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            error_message = self._error_message(error_body)
            logger.warning(
                "OpenAI HTTP error",
                extra=self._log_extra(
                    payload,
                    status_code=exc.code,
                    error_message=error_message,
                ),
            )
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
            logger.warning(
                "OpenAI network error",
                extra=self._log_extra(
                    payload,
                    error_message=str(exc.reason),
                ),
            )
            raise LLMProviderError(
                f"OpenAI API request failed: {exc.reason}",
                retryable=True,
            ) from exc

        try:
            data = json.loads(response_body)
        except json.JSONDecodeError as exc:
            logger.warning(
                "OpenAI returned invalid JSON",
                extra=self._log_extra(payload, error_message=str(exc)),
            )
            raise LLMProviderError(
                f"OpenAI API returned invalid JSON: {exc}",
                retryable=True,
            ) from exc

        if not isinstance(data, dict):
            logger.warning(
                "OpenAI returned unexpected response shape",
                extra=self._log_extra(payload),
            )
            raise LLMProviderError(
                "OpenAI API returned an unexpected response shape.",
                retryable=True,
            )
        api_error = self._extract_api_error(data)
        if api_error is not None:
            logger.warning(
                "OpenAI API reported an error",
                extra=self._log_extra(payload, response=data, error_message=api_error),
            )
            raise LLMProviderError(
                f"OpenAI API error: {api_error}",
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

    def _raise_for_incomplete_response(self, response: Mapping[str, Any]) -> None:
        status = response.get("status")
        if status != "incomplete":
            return

        incomplete_details = response.get("incomplete_details")
        reason = None
        if isinstance(incomplete_details, dict):
            raw_reason = incomplete_details.get("reason")
            if isinstance(raw_reason, str) and raw_reason.strip():
                reason = raw_reason.strip()

        error_message = "OpenAI response was incomplete."
        retryable = True
        if reason == "max_output_tokens":
            error_message = (
                "OpenAI response was incomplete because max_output_tokens was reached."
            )
            retryable = False
        elif reason:
            error_message = f"OpenAI response was incomplete: {reason}."

        logger.warning(
            "OpenAI response incomplete",
            extra={
                "openai_response_status": status,
                "openai_incomplete_reason": reason,
            },
        )
        raise LLMProviderError(error_message, retryable=retryable)

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
            error_message = self._extract_api_error(data)
            if error_message:
                return error_message
        return error_body.strip() or "No error body returned."

    def _extract_api_error(self, data: Mapping[str, Any]) -> str | None:
        error = data.get("error")
        if error is None:
            return None
        if isinstance(error, str):
            stripped = error.strip()
            return stripped or None
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
            serialized = json.dumps(error, sort_keys=True)
            return serialized if serialized != "{}" else None
        if error:
            return str(error)
        return None

    def _log_extra(
        self,
        payload: Mapping[str, Any],
        *,
        response: Mapping[str, Any] | None = None,
        status_code: int | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        input_items = payload.get("input")
        message_count = len(input_items) if isinstance(input_items, list) else 0
        input_chars = 0
        if isinstance(input_items, list):
            for item in input_items:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if isinstance(content, str):
                    input_chars += len(content)

        extra: dict[str, Any] = {
            "llm_provider": self.provider_name,
            "llm_model": payload.get("model"),
            "openai_message_count": message_count,
            "openai_input_chars": input_chars,
            "openai_has_schema": "text" in payload,
            "openai_max_output_tokens": payload.get("max_output_tokens"),
            "openai_temperature": payload.get("temperature"),
        }
        if status_code is not None:
            extra["status_code"] = status_code
        if error_message is not None:
            extra["error_message"] = error_message
        if response is not None:
            extra["openai_response_id"] = response.get("id")
            extra["openai_response_status"] = response.get("status")
            incomplete_details = response.get("incomplete_details")
            if isinstance(incomplete_details, dict):
                extra["openai_incomplete_reason"] = incomplete_details.get("reason")
            usage = response.get("usage")
            if isinstance(usage, dict):
                extra["openai_input_tokens"] = usage.get("input_tokens")
                extra["openai_output_tokens"] = usage.get("output_tokens")
                extra["openai_total_tokens"] = usage.get("total_tokens")
        return extra

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
