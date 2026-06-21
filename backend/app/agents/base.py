from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, ValidationError

from backend.app.orchestrator.schemas import (
    AgentName,
    AgentOutputContent,
    AgentResult,
    AgentStatus,
    AnalysisContext,
    CostTrace,
    OpenAlphaSchema,
    utc_now,
)


OutputT = TypeVar("OutputT", bound=BaseModel)


class AgentOutputValidationError(ValueError):
    """Raised when an agent returns output that does not match its schema."""


class AgentExecutionPayload(OpenAlphaSchema):
    status: AgentStatus = "completed"
    provider: str | None = Field(default=None, min_length=1, max_length=64)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0, ge=0)
    output: Any | None = None
    data_used: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    parsing_errors: list[str] = Field(default_factory=list)
    agent_name: str | None = Field(default=None, min_length=1, max_length=64)


class BaseAgent(ABC, Generic[OutputT]):
    name: AgentName
    output_schema: type[OutputT] | None = None

    def __init__(
        self,
        *,
        name: AgentName | None = None,
        provider: str | None = None,
        model: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        resolved_name = name or getattr(self, "name", None)
        if resolved_name is None:
            raise ValueError("agent name is required")

        self.name = resolved_name
        self.provider = provider
        self.model = model
        self.logger = logger or logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    async def run(self, context: AnalysisContext) -> AgentResult:
        started_at = utc_now()
        payload: AgentExecutionPayload | None = None
        provider = self._resolve_provider(context, None)
        model = self._resolve_model(context, None)

        self.logger.info(
            "Agent started",
            extra={"agent_name": self.name, "run_id": context.run_id},
        )

        try:
            payload = await self.execute(context)
            provider = self._resolve_provider(context, payload.provider)
            model = self._resolve_model(context, payload.model)
            output = self.validate_output(payload.output)
            result = AgentResult(
                agent_name=self.name,
                status=payload.status,
                provider=provider,
                model=model,
                input_tokens=payload.input_tokens,
                output_tokens=payload.output_tokens,
                estimated_cost_usd=payload.estimated_cost_usd,
                started_at=started_at,
                finished_at=utc_now(),
                output=output,
                data_used=payload.data_used,
                warnings=payload.warnings,
                parsing_errors=payload.parsing_errors,
            )
        except (AgentOutputValidationError, ValidationError) as exc:
            result = self._failure_result(
                started_at=started_at,
                provider=provider,
                model=model,
                payload=payload,
                error_message=str(exc),
                parsing_errors=[str(exc)],
            )
        except Exception as exc:
            self.logger.exception(
                "Agent failed",
                extra={"agent_name": self.name, "run_id": context.run_id},
            )
            result = self._failure_result(
                started_at=started_at,
                provider=provider,
                model=model,
                payload=payload,
                error_message=str(exc),
            )

        self._record_result(context, result)
        if result.status == "failed":
            self.logger.warning(
                "Agent failed",
                extra={"agent_name": self.name, "run_id": context.run_id},
            )
        else:
            self.logger.info(
                "Agent finished",
                extra={"agent_name": self.name, "run_id": context.run_id},
            )
        return result

    @abstractmethod
    async def execute(self, context: AnalysisContext) -> AgentExecutionPayload:
        raise NotImplementedError

    def validate_output(self, output: Any | None) -> AgentOutputContent | None:
        if output is None:
            return None
        if self.output_schema is None:
            return output
        if isinstance(output, self.output_schema):
            return output
        try:
            return self.output_schema.model_validate(output)
        except ValidationError as exc:
            raise AgentOutputValidationError(
                (
                    f"{self.name} output failed "
                    f"{self.output_schema.__name__} validation: {exc}"
                )
            ) from exc

    def _failure_result(
        self,
        *,
        started_at: datetime,
        provider: str,
        model: str,
        payload: AgentExecutionPayload | None,
        error_message: str,
        parsing_errors: Sequence[str] = (),
    ) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            status="failed",
            provider=provider,
            model=model,
            input_tokens=payload.input_tokens if payload else 0,
            output_tokens=payload.output_tokens if payload else 0,
            estimated_cost_usd=payload.estimated_cost_usd if payload else 0,
            started_at=started_at,
            finished_at=utc_now(),
            data_used=payload.data_used if payload else [],
            warnings=payload.warnings if payload else [],
            parsing_errors=list(parsing_errors)
            + (payload.parsing_errors if payload else []),
            error_message=error_message,
        )

    def _record_result(self, context: AnalysisContext, result: AgentResult) -> None:
        context.agent_results.append(result)
        context.cost_traces.append(
            CostTrace(
                provider=result.provider,
                model=result.model,
                agent_name=result.agent_name,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                estimated_cost_usd=result.estimated_cost_usd,
            )
        )
        context.updated_at = result.finished_at or utc_now()

    def _resolve_provider(self, context: AnalysisContext, provider: str | None) -> str:
        return provider or self.provider or context.request.llm_provider

    def _resolve_model(self, context: AnalysisContext, model: str | None) -> str:
        return model or self.model or context.request.llm_model
