from __future__ import annotations

import asyncio

import pytest

from backend.app.agents.base import AgentExecutionPayload, BaseAgent
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    AnalysisRequest,
    RiskReviewAgentOutput,
)


def make_context() -> AnalysisContext:
    return AnalysisContext(
        run_id="run_1",
        request=AnalysisRequest(
            symbol="AAPL",
            horizon="1m",
            llm_model="gpt-4.1-mini",
        ),
    )


class SuccessfulRiskAgent(BaseAgent[RiskReviewAgentOutput]):
    name = "risk_review_agent"
    output_schema = RiskReviewAgentOutput

    async def execute(self, context: AnalysisContext) -> AgentExecutionPayload:
        return AgentExecutionPayload(
            provider="openai",
            model="gpt-4.1-mini",
            input_tokens=100,
            output_tokens=30,
            estimated_cost_usd=0.001,
            data_used=["market_data"],
            output={
                "risk_level": "medium",
                "confidence": 0.7,
                "summary": "Risk is balanced but not negligible.",
                "key_risks": ["Valuation sensitivity"],
            },
        )


class InvalidOutputAgent(BaseAgent[RiskReviewAgentOutput]):
    name = "risk_review_agent"
    output_schema = RiskReviewAgentOutput

    async def execute(self, context: AnalysisContext) -> AgentExecutionPayload:
        return AgentExecutionPayload(
            input_tokens=20,
            output_tokens=10,
            estimated_cost_usd=0.0002,
            output={
                "risk_level": "medium",
                "confidence": 2,
                "summary": "Invalid confidence should fail validation.",
            },
        )


class ExplodingAgent(BaseAgent[RiskReviewAgentOutput]):
    name = "risk_review_agent"
    output_schema = RiskReviewAgentOutput

    async def execute(self, context: AnalysisContext) -> AgentExecutionPayload:
        raise RuntimeError("provider unavailable")


def test_base_agent_records_successful_result_and_cost_trace() -> None:
    context = make_context()
    result = asyncio.run(SuccessfulRiskAgent().run(context))

    assert result.status == "completed"
    assert result.agent_name == "risk_review_agent"
    assert result.output is not None
    assert result.estimated_cost_usd == pytest.approx(0.001)
    assert context.agent_results == [result]
    assert len(context.cost_traces) == 1
    assert context.total_cost_usd == pytest.approx(0.001)


def test_base_agent_converts_invalid_output_to_failed_result() -> None:
    context = make_context()
    result = asyncio.run(InvalidOutputAgent().run(context))

    assert result.status == "failed"
    assert result.error_message
    assert result.parsing_errors
    assert result.input_tokens == 20
    assert result.estimated_cost_usd == pytest.approx(0.0002)
    assert context.agent_results == [result]
    assert context.cost_traces[0].estimated_cost_usd == pytest.approx(0.0002)


def test_base_agent_converts_unexpected_exception_to_failed_result() -> None:
    context = make_context()
    result = asyncio.run(ExplodingAgent().run(context))

    assert result.status == "failed"
    assert result.error_message == "provider unavailable"
    assert result.provider == "openai"
    assert result.model == "gpt-4.1-mini"
    assert context.agent_results == [result]
    assert len(context.cost_traces) == 1
