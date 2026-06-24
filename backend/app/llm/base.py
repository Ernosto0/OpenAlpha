from __future__ import annotations

import asyncio
import json
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


ProviderOperation = Callable[[], Awaitable["LLMResult"]]
TModel = TypeVar("TModel", bound=BaseModel)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_provider_name(provider_name: str) -> str:
    normalized = provider_name.strip().lower()
    return "ollama" if normalized == "local" else normalized


class LLMProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class LLMConfigurationError(LLMProviderError):
    pass


class LLMResponseValidationError(LLMProviderError):
    pass


class LLMMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("message content must not be empty")
        return stripped


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class LLMHealthCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=64)
    available: bool
    message: str = Field(min_length=1, max_length=500)
    checked_at: datetime = Field(default_factory=utc_now)
    base_url: str | None = Field(default=None, max_length=300)
    raw_response: dict[str, Any] | None = None


class LLMModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=160)
    provider: str = Field(min_length=1, max_length=64)
    installed: bool = True
    size_bytes: int | None = Field(default=None, ge=0)
    family: str | None = Field(default=None, max_length=120)
    parameter_size: str | None = Field(default=None, max_length=120)
    quantization_level: str | None = Field(default=None, max_length=120)
    modified_at: datetime | None = None
    raw: dict[str, Any] | None = None


class LLMResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=120)
    agent_name: str = Field(default="unknown", min_length=1, max_length=120)
    content: Any | None = None
    raw_content: str | None = None
    raw_response: dict[str, Any] | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0, ge=0)
    cost_type: str = Field(default="api", min_length=1, max_length=64)
    duration_ms: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    warnings: list[str] = Field(default_factory=list)
    parsing_errors: list[str] = Field(default_factory=list)
    error_message: str | None = None

    @classmethod
    def failed(
        cls,
        *,
        provider: str,
        model: str,
        agent_name: str,
        error_message: str,
        cost_type: str = "api",
        duration_ms: int = 0,
        warnings: Sequence[str] = (),
        parsing_errors: Sequence[str] = (),
    ) -> "LLMResult":
        return cls(
            provider=provider,
            model=model,
            agent_name=agent_name,
            error_message=error_message,
            cost_type=cost_type,
            duration_ms=duration_ms,
            warnings=list(warnings),
            parsing_errors=list(parsing_errors),
        )


class BaseLLMProvider(ABC):
    provider_name: str

    def __init__(
        self,
        *,
        default_model: str | None = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be greater than or equal to 0")
        if retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be greater than or equal to 0")

        self.default_model = default_model
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    async def health_check(self) -> LLMHealthCheckResult:
        return LLMHealthCheckResult(
            provider=self.provider_name,
            available=False,
            message=f"{self.provider_name} does not expose a health check.",
        )

    async def list_models(self) -> list[LLMModelInfo]:
        return []

    @abstractmethod
    async def generate(
        self,
        *,
        messages: Sequence[LLMMessage | Mapping[str, str]],
        model: str | None = None,
        agent_name: str = "unknown",
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResult:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    def resolve_model(self, model: str | None) -> str:
        resolved = (model or self.default_model or "").strip()
        if not resolved:
            raise LLMConfigurationError(
                f"{self.provider_name} model is required",
                retryable=False,
            )
        return resolved

    def normalize_messages(
        self,
        messages: Sequence[LLMMessage | Mapping[str, str]],
    ) -> list[LLMMessage]:
        if not messages:
            raise ValueError("messages must not be empty")
        return [
            message
            if isinstance(message, LLMMessage)
            else LLMMessage.model_validate(message)
            for message in messages
        ]

    def calculate_cost(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> tuple[float, list[str]]:
        return 0.0, [f"No pricing configured for {self.provider_name}/{model}."]

    def validate_json_content(
        self,
        raw_content: str,
        output_schema: type[TModel],
    ) -> TModel:
        normalized_content = self.normalize_json_text(raw_content)
        try:
            return output_schema.model_validate_json(normalized_content)
        except ValidationError as exc:
            raise LLMResponseValidationError(
                f"LLM JSON response failed {output_schema.__name__} validation: {exc}",
                retryable=True,
            ) from exc
        except ValueError as exc:
            raise LLMResponseValidationError(
                f"LLM response was not valid JSON: {exc}",
                retryable=True,
            ) from exc

    def normalize_json_text(self, raw_content: str) -> str:
        stripped = raw_content.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
            stripped = stripped.strip()

        start = min(
            (
                index
                for index in (stripped.find("{"), stripped.find("["))
                if index != -1
            ),
            default=-1,
        )
        if start > 0:
            stripped = stripped[start:].strip()
        return stripped

    def validate_json_dict(
        self,
        content: dict[str, Any],
        output_schema: type[TModel],
    ) -> TModel:
        try:
            return output_schema.model_validate(content)
        except ValidationError as exc:
            formatted = json.dumps(content, sort_keys=True)
            raise LLMResponseValidationError(
                (
                    f"LLM JSON object failed {output_schema.__name__} validation: "
                    f"{exc}; content={formatted}"
                ),
                retryable=True,
            ) from exc

    async def _run_with_retries(self, operation: ProviderOperation) -> LLMResult:
        last_error: LLMProviderError | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return await operation()
            except LLMProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt >= self.max_retries:
                    raise

                delay = self.retry_backoff_seconds * (2**attempt)
                if delay:
                    await asyncio.sleep(delay)

        if last_error is not None:
            raise last_error
        raise LLMProviderError("LLM operation failed without an error")

    def estimate_tokens(self, text: str) -> int:
        stripped = text.strip()
        if not stripped:
            return 0
        return max(1, len(stripped) // 4)

    def start_timer(self) -> float:
        return time.perf_counter()

    def elapsed_ms(self, started_at: float) -> int:
        return max(0, int(round((time.perf_counter() - started_at) * 1000)))


def should_stop_analysis_for_llm_error(exc: LLMProviderError) -> bool:
    if isinstance(exc, LLMConfigurationError):
        return True

    status_code = getattr(exc, "status_code", None)
    if status_code in {401, 403, 429}:
        return True

    message = str(exc).lower()
    fatal_markers = (
        "quota exceeded",
        "exceeded your current quota",
        "api key is missing",
        "invalid api key",
        "unauthorized",
        "forbidden",
        "authentication failed",
        "invalid authentication",
    )
    return any(marker in message for marker in fatal_markers)
