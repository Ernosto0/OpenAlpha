from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from backend.app.llm.base import (
    BaseLLMProvider,
    LLMConfigurationError,
    LLMHealthCheckResult,
    LLMMessage,
    LLMModelInfo,
    LLMProviderError,
    LLMResponseValidationError,
    LLMResult,
    TokenUsage,
    TModel,
)


OllamaTransport = Callable[
    [str, str, Mapping[str, str], Mapping[str, Any] | None, float],
    Mapping[str, Any] | Awaitable[Mapping[str, Any]],
]


class OllamaProvider(BaseLLMProvider):
    provider_name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        default_model: str | None = None,
        timeout_seconds: float = 60,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        transport: OllamaTransport | None = None,
    ) -> None:
        super().__init__(
            default_model=default_model,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
        )
        self.base_url = self._normalize_base_url(base_url)
        self.timeout_seconds = timeout_seconds
        self._transport = transport or self._request_json

    async def health_check(self) -> LLMHealthCheckResult:
        try:
            response = await self._send_request("GET", "/api/tags", payload=None)
        except LLMProviderError as exc:
            return LLMHealthCheckResult(
                provider=self.provider_name,
                available=False,
                message=str(exc),
                base_url=self.base_url,
            )

        models = response.get("models")
        model_count = len(models) if isinstance(models, list) else 0
        message = (
            f"Ollama is reachable at {self.base_url} with {model_count} installed model(s)."
        )
        return LLMHealthCheckResult(
            provider=self.provider_name,
            available=True,
            message=message,
            base_url=self.base_url,
            raw_response=dict(response),
        )

    async def list_models(self) -> list[LLMModelInfo]:
        response = await self._send_request("GET", "/api/tags", payload=None)
        models = response.get("models")
        if not isinstance(models, list):
            return []

        normalized: list[LLMModelInfo] = []
        for model in models:
            if not isinstance(model, dict):
                continue
            name = self._coerce_text(model.get("name")) or self._coerce_text(model.get("model"))
            if not name:
                continue
            details = model.get("details")
            details_dict = details if isinstance(details, dict) else {}
            normalized.append(
                LLMModelInfo(
                    id=name,
                    label=name,
                    provider=self.provider_name,
                    installed=True,
                    size_bytes=self._coerce_int(model.get("size")),
                    family=self._coerce_text(details_dict.get("family")),
                    parameter_size=self._coerce_text(details_dict.get("parameter_size")),
                    quantization_level=self._coerce_text(
                        details_dict.get("quantization_level")
                    ),
                    modified_at=self._coerce_datetime(model.get("modified_at")),
                    raw=dict(model),
                )
            )
        return normalized

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
            payload = self._build_chat_payload(
                messages=messages,
                model=resolved_model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            response = await self._send_request("POST", "/api/chat", payload=payload)
            raw_content = self._extract_chat_content(response)
            usage = self._extract_usage(response, raw_content)
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
                estimated_cost_usd=0,
                cost_type="local",
                duration_ms=self.elapsed_ms(started),
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
        resolved_model = self.resolve_model(model)
        started = self.start_timer()
        schema = self._normalize_schema(output_schema.model_json_schema())
        normalized_messages = self.normalize_messages(messages)
        warnings: list[str] = []
        parsing_errors: list[str] = []
        last_raw_content = ""
        last_response: Mapping[str, Any] | None = None
        last_usage = TokenUsage()

        for attempt in range(2):
            attempt_messages = list(normalized_messages)
            if attempt == 0:
                attempt_messages.append(
                    LLMMessage(
                        role="user",
                        content=(
                            "Return valid JSON only. Do not include markdown or prose. "
                            f"The JSON must satisfy this schema: {json.dumps(schema, sort_keys=True)}"
                        ),
                    )
                )
            else:
                attempt_messages.append(
                    LLMMessage(
                        role="user",
                        content=(
                            "Your previous response was invalid. Return corrected JSON only. "
                            f"Validation/parsing error: {parsing_errors[-1]}"
                        ),
                    )
                )

            payload = self._build_chat_payload(
                messages=attempt_messages,
                model=resolved_model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_format={"type": "json_schema", "json_schema": schema},
            )
            response = await self._send_request_with_retries(
                "POST",
                "/api/chat",
                payload=payload,
            )
            last_response = response
            raw_content = self._extract_chat_content(response)
            last_raw_content = raw_content
            last_usage = self._extract_usage(response, raw_content)
            try:
                content = self.validate_json_content(raw_content, output_schema)
            except LLMResponseValidationError as exc:
                parsing_errors.append(str(exc))
                if attempt == 0:
                    warnings.append(
                        "Ollama returned invalid structured output on the first attempt; retrying once."
                    )
                    continue
                warning = "Ollama structured output remained invalid after one retry."
                return LLMResult.failed(
                    provider=self.provider_name,
                    model=resolved_model,
                    agent_name=agent_name,
                    error_message=str(exc),
                    cost_type="local",
                    duration_ms=self.elapsed_ms(started),
                    warnings=[*warnings, warning],
                    parsing_errors=parsing_errors,
                ).model_copy(
                    update={
                        "raw_content": last_raw_content,
                        "raw_response": dict(last_response),
                        "input_tokens": last_usage.input_tokens,
                        "output_tokens": last_usage.output_tokens,
                        "total_tokens": last_usage.total_tokens,
                    }
                )

            return LLMResult(
                provider=self.provider_name,
                model=resolved_model,
                agent_name=agent_name,
                content=content,
                raw_content=raw_content,
                raw_response=dict(response),
                input_tokens=last_usage.input_tokens,
                output_tokens=last_usage.output_tokens,
                total_tokens=last_usage.total_tokens,
                estimated_cost_usd=0,
                cost_type="local",
                duration_ms=self.elapsed_ms(started),
                warnings=warnings,
                parsing_errors=parsing_errors,
            )

        raise AssertionError("unreachable")

    async def _send_request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None,
    ) -> Mapping[str, Any]:
        result = self._transport(
            method,
            f"{self.base_url}{path}",
            {"Content-Type": "application/json"},
            payload,
            self.timeout_seconds,
        )
        if asyncio.iscoroutine(result):
            result = await result
        if not isinstance(result, Mapping):
            raise LLMProviderError(
                "Ollama returned an unexpected response shape.",
                retryable=True,
            )
        return result

    async def _send_request_with_retries(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None,
    ) -> Mapping[str, Any]:
        last_error: LLMProviderError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await self._send_request(method, path, payload=payload)
            except LLMProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt >= self.max_retries:
                    raise
                delay = self.retry_backoff_seconds * (2**attempt)
                if delay:
                    await asyncio.sleep(delay)
        if last_error is not None:
            raise last_error
        raise LLMProviderError("Ollama request failed without an error.")

    async def _request_json(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(
            self._request_json_sync,
            method,
            url,
            headers,
            payload,
            timeout_seconds,
        )

    def _request_json_sync(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers=dict(headers),
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except TimeoutError as exc:
            raise LLMProviderError(
                f"Ollama request timed out at {self.base_url}.",
                retryable=True,
            ) from exc
        except ValueError as exc:
            raise LLMConfigurationError(
                f"Ollama base URL is invalid: {self.base_url}",
                retryable=False,
            ) from exc
        except urllib.error.HTTPError as exc:
            error_message = self._read_http_error(exc)
            retryable = exc.code in {408, 429, 500, 502, 503, 504}
            raise LLMProviderError(
                f"Ollama request failed with HTTP {exc.code}: {error_message}",
                retryable=retryable,
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            reason = str(exc.reason)
            if "timed out" in reason.lower():
                raise LLMProviderError(
                    f"Ollama request timed out at {self.base_url}.",
                    retryable=True,
                ) from exc
            raise LLMProviderError(
                f"Ollama is not reachable at {self.base_url}: {reason}",
                retryable=False,
            ) from exc

        try:
            data = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                f"Ollama returned invalid JSON: {exc}",
                retryable=True,
            ) from exc
        if not isinstance(data, dict):
            raise LLMProviderError(
                "Ollama returned an unexpected response shape.",
                retryable=True,
            )
        return data

    def _build_chat_payload(
        self,
        *,
        messages: Sequence[LLMMessage | Mapping[str, str]],
        model: str,
        temperature: float | None,
        max_output_tokens: int | None,
        response_format: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in self.normalize_messages(messages)
            ],
        }
        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_output_tokens is not None:
            options["num_predict"] = max_output_tokens
        if options:
            payload["options"] = options
        if response_format is not None:
            payload["format"] = response_format
        return payload

    def _extract_chat_content(self, response: Mapping[str, Any]) -> str:
        message = response.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        raise LLMResponseValidationError(
            "Ollama response did not include assistant content.",
            retryable=True,
        )

    def _extract_usage(self, response: Mapping[str, Any], raw_content: str) -> TokenUsage:
        prompt_tokens = self._coerce_int(response.get("prompt_eval_count"))
        completion_tokens = self._coerce_int(response.get("eval_count"))
        if prompt_tokens == 0:
            serialized_prompt = json.dumps(response.get("message", {}), sort_keys=True)
            prompt_tokens = self.estimate_tokens(serialized_prompt)
        if completion_tokens == 0:
            completion_tokens = self.estimate_tokens(raw_content)
        return TokenUsage(
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    def _normalize_schema(self, node: Any) -> Any:
        if isinstance(node, list):
            return [self._normalize_schema(item) for item in node]
        if not isinstance(node, dict):
            return node
        normalized = {
            key: self._normalize_schema(value)
            for key, value in node.items()
            if key != "default"
        }
        properties = normalized.get("properties")
        if isinstance(properties, dict):
            normalized["required"] = list(properties.keys())
            normalized.setdefault("additionalProperties", False)
        return normalized

    def _read_http_error(self, exc: urllib.error.HTTPError) -> str:
        error_body = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(error_body)
        except json.JSONDecodeError:
            return error_body.strip() or f"HTTP {exc.code}"
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, str) and error.strip():
                return error.strip()
        return error_body.strip() or f"HTTP {exc.code}"

    def _normalize_base_url(self, base_url: str) -> str:
        normalized = base_url.strip().rstrip("/")
        if not normalized:
            raise LLMConfigurationError("Ollama base URL is required.", retryable=False)
        parsed = urllib.parse.urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise LLMConfigurationError(
                f"Ollama base URL is invalid: {base_url}",
                retryable=False,
            )
        return normalized

    def _coerce_text(self, value: Any) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return None

    def _coerce_int(self, value: Any) -> int:
        return value if isinstance(value, int) and value >= 0 else 0

    def _coerce_datetime(self, value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


__all__ = ["OllamaProvider"]
