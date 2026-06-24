from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from backend.app.agents.base import AgentExecutionPayload, BaseAgent
from backend.app.llm import BaseLLMProvider, LLMProviderError
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    BearCaseAgentOutput,
    BullCaseAgentOutput,
    NewsSentimentOutput,
    RiskReviewAgentOutput,
    TechnicalAgentOutput,
)


RISK_REVIEW_AGENT_SYSTEM_PROMPT = """
You are the Risk Review Agent for OpenAlpha, a local-first AI equity research application.

Your job is to review risk using the existing Technical Research Agent output, News & Sentiment Agent output, Bull Case Agent output, Bear Case Agent output, and Data Collector quality output.

You are not the final decision-maker. You do not produce the final AI view, final investment thesis, or final user-facing report. The Thesis Agent and Report Writer Agent will do that later.

Your task is to assign a research risk level, produce a numeric risk score, identify the main risks, identify invalidation conditions, and recommend a confidence adjustment when data quality is low or evidence is weak.

Core rules:

* Use only the provided agent outputs and data quality information.
* Do not fetch external data.
* Do not calculate new indicators.
* Do not invent company facts, risks, news, catalysts, support levels, or resistance levels.
* Do not provide personalized financial advice.
* Do not recommend buying, selling, holding, shorting, or investing.
* Do not use language like "buy now", "sell now", "guaranteed", "risk-free", or "you should invest".
* Use research language such as "risk level", "risk score", "invalidation condition", "data limitation", "confidence adjustment", and "uncertainty".
* If previous agent outputs are missing or failed, reflect that in risk_score, main_risks, invalidation_conditions, and confidence_adjustment.
* If data quality is low, stale, incomplete, or provider coverage is weak, reduce confidence.
* If technical and news outputs conflict, increase risk or uncertainty.
* If bull and bear cases are both strong, classify the setup as higher risk or mixed-risk.
* If there is insufficient data, return risk_level = "insufficient_data" and a high confidence reduction.
* Output valid JSON only.
* Do not include markdown.
* Do not include explanations outside the JSON object.

Allowed values for risk_level:

* low
* moderate
* high
* very_high
* insufficient_data

Risk score rules:

* risk_score must be a number between 0 and 100.
* 0-24 means low risk.
* 25-49 means moderate risk.
* 50-74 means high risk.
* 75-100 means very high risk.
* Use insufficient_data when missing or unreliable inputs prevent a meaningful risk review.
* Do not assign low risk when data quality is poor.
* Do not assign low risk when news is missing and technical signals are weak or mixed.
* Do not assign low risk when downside conditions are severe or invalidation levels are close.

Confidence adjustment rules:

* confidence_adjustment must be a number between -0.40 and 0.00.
* Use 0.00 when data quality is strong and evidence is consistent.
* Use -0.05 when there are minor limitations.
* Use -0.10 to -0.15 when evidence is mixed or some data is missing.
* Use -0.20 to -0.30 when important data is missing, stale, or low quality.
* Use -0.35 to -0.40 when the analysis is mostly unreliable or insufficient.
* Never increase confidence in this agent. This agent can only reduce or preserve confidence.

Risk interpretation guidance:

* Technical risks may include weak trend structure, bearish momentum, failed breakouts, price near resistance, support breaks, high volatility, or weak volume confirmation.
* News risks may include negative sentiment, missing news coverage, stale news, low-quality sources, unclear relevance, or negative company-specific developments.
* Data risks may include missing price history, limited lookback period, stale timestamps, failed providers, missing news, missing profile data, or low data quality score.
* Bull/bear balance risks may include one-sided evidence, conflicting evidence, overreliance on technicals, weak catalyst support, or a strong bear case against a weak bull case.
* Invalidation conditions should be observable and testable when possible.
* Invalidation conditions should describe what would weaken or invalidate the current research view, not tell the user what action to take.

Return exactly this JSON shape:

{
"risk_level": "low | moderate | high | very_high | insufficient_data",
"risk_score": 0,
"main_risks": [
"Main risk 1",
"Main risk 2",
"Main risk 3"
],
"invalidation_conditions": [
"Condition that would invalidate or weaken the current research view 1",
"Condition that would invalidate or weaken the current research view 2",
"Condition that would invalidate or weaken the current research view 3"
],
"confidence_adjustment": -0.1
}

If there is insufficient data, return:

{
"risk_level": "insufficient_data",
"risk_score": 85,
"main_risks": [
"The available data is insufficient to make a reliable risk assessment."
],
"invalidation_conditions": [
"A meaningful risk review requires usable technical data, news data, or clearly documented data quality inputs."
],
"confidence_adjustment": -0.35
}
""".strip()


RISK_REVIEW_AGENT_USER_PROMPT = """Review the risk profile for {symbol} using the provided agent outputs.

Context:

* Symbol: {symbol}
* Company name: {company_name}
* Market: {market}
* Time horizon: {horizon}
* Analysis depth: {analysis_depth}
* Latest close price: {latest_close}
* Latest price timestamp: {latest_price_timestamp}

Data quality:

* Overall data quality score: {data_quality_score}
* Price data status: {price_data_status}
* News data status: {news_data_status}
* Company profile status: {company_profile_status}
* Missing data: {missing_data}
* Provider names: {provider_names}
* Data quality warnings: {data_quality_warnings}

Technical Research Agent output:
{technical_agent_output}

News & Sentiment Agent output:
{news_sentiment_agent_output}

Bull Case Agent output:
{bull_case_agent_output}

Bear Case Agent output:
{bear_case_agent_output}

Failed or missing agent outputs:
{failed_agent_outputs}

Important constraints:

* Use only the provided context and agent outputs.
* Do not fetch external data.
* Do not calculate new indicators.
* Do not invent missing facts, risks, catalysts, or news.
* Do not provide personalized financial advice.
* Do not produce the final thesis or final AI view.
* Assign a risk level and numeric risk score.
* Identify the most important risks.
* Identify observable invalidation conditions.
* Reduce confidence when data quality is low, evidence is weak, or prior agents failed.
* Return valid JSON only using the required RiskReviewOutput shape.
"""


class RiskReviewAgent(BaseAgent[RiskReviewAgentOutput]):
    name = "risk_review_agent"
    output_schema = RiskReviewAgentOutput

    def __init__(
        self,
        *,
        llm_provider: BaseLLMProvider | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 900,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.llm_provider = llm_provider
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    async def execute(self, context: AnalysisContext) -> AgentExecutionPayload:
        if self._has_no_usable_inputs(context):
            output = RiskReviewAgentOutput(
                risk_level="insufficient_data",
                risk_score=85,
                main_risks=[
                    "The available data is insufficient to make a reliable risk assessment."
                ],
                invalidation_conditions=[
                    "A meaningful risk review requires usable technical data, news data, or clearly documented data quality inputs."
                ],
                confidence_adjustment=-0.35,
            )
            context.risk_review_output = output
            return AgentExecutionPayload(
                status="partial",
                provider="deterministic",
                model="deterministic",
                cost_type="deterministic",
                output=output,
                data_used=[],
                warnings=[
                    "Risk review was generated without usable upstream inputs."
                ],
            )

        provider = self.llm_provider or self._create_llm_provider(
            context.request.llm_provider
        )
        try:
            result = await provider.generate_json(
                messages=[
                    {"role": "system", "content": RISK_REVIEW_AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": self.build_user_prompt(context)},
                ],
                output_schema=RiskReviewAgentOutput,
                model=context.request.llm_model,
                agent_name=self.name,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
            )
        except LLMProviderError as exc:
            if self._should_stop_on_llm_error(exc):
                raise
            output = self._fallback_output_for_llm_failure(context, str(exc))
            context.risk_review_output = output
            return AgentExecutionPayload(
                status="partial",
                provider="deterministic",
                model="deterministic",
                cost_type="deterministic",
                output=output,
                data_used=self._data_used(context),
                warnings=self._dedupe(
                    [
                        "Risk review used a deterministic fallback because the LLM request failed.",
                        f"LLM error: {exc}",
                        *self._input_warnings(context),
                    ]
                ),
            )

        output = self.validate_output(result.content)
        if not isinstance(output, RiskReviewAgentOutput):
            raise TypeError("risk review agent returned an unexpected output type")

        context.risk_review_output = output
        warnings = self._dedupe([*result.warnings, *self._input_warnings(context)])

        return AgentExecutionPayload(
            status="completed",
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            cost_type=result.cost_type,
            duration_ms=result.duration_ms,
            output=output,
            data_used=self._data_used(context),
            warnings=warnings,
            parsing_errors=result.parsing_errors,
        )

    def _fallback_output_for_llm_failure(
        self,
        context: AnalysisContext,
        error_message: str,
    ) -> RiskReviewAgentOutput:
        return RiskReviewAgentOutput(
            risk_level="insufficient_data",
            risk_score=85,
            main_risks=[
                "The risk review could not be fully synthesized because the LLM-backed risk analysis step failed.",
                "Upstream evidence may be present but was not fully integrated into a structured risk judgment.",
                f"LLM error: {error_message}",
            ],
            invalidation_conditions=[
                "Restore LLM access so the collected technical, sentiment, bull, and bear inputs can be re-evaluated together.",
                "Re-run the analysis after confirming upstream inputs are still available and current.",
            ],
            confidence_adjustment=-0.35,
        )

    def build_user_prompt(self, context: AnalysisContext) -> str:
        prompt = RISK_REVIEW_AGENT_USER_PROMPT.format(
            symbol=context.request.symbol,
            company_name=self._company_name(context) or "Unknown",
            market=context.request.market,
            horizon=context.request.horizon,
            analysis_depth=context.request.depth,
            latest_close=self._latest_close(context),
            latest_price_timestamp=self._latest_price_timestamp(context),
            data_quality_score=self._data_quality_score(context),
            price_data_status=self._price_data_status(context),
            news_data_status=self._news_data_status(context),
            company_profile_status=self._company_profile_status(context),
            missing_data=self._join_or_none(self._missing_data(context)),
            provider_names=self._join_or_none(self._provider_names(context)),
            data_quality_warnings=self._join_or_none(self._data_quality_warnings(context)),
            technical_agent_output=self._technical_output_text(context.technical_output),
            news_sentiment_agent_output=self._news_output_text(
                context.news_sentiment_output
            ),
            bull_case_agent_output=self._bull_case_output_text(context.bull_case_output),
            bear_case_agent_output=self._bear_case_output_text(context.bear_case_output),
            failed_agent_outputs=self._join_or_none(self._failed_or_missing_outputs(context)),
        )

        structured_payload = {
            "technical_output": context.technical_output.model_dump(mode="json")
            if context.technical_output is not None
            else None,
            "news_sentiment_output": context.news_sentiment_output.model_dump(
                mode="json"
            )
            if context.news_sentiment_output is not None
            else None,
            "bull_case_output": context.bull_case_output.model_dump(mode="json")
            if context.bull_case_output is not None
            else None,
            "bear_case_output": context.bear_case_output.model_dump(mode="json")
            if context.bear_case_output is not None
            else None,
            "data_quality": context.data_quality.model_dump(mode="json")
            if context.data_quality is not None
            else None,
            "context_warnings": context.warnings,
        }

        prompt += (
            "\n\nStructured upstream payload:\n"
            f"{json.dumps(structured_payload, indent=2, sort_keys=True)}"
        )
        if context.request.custom_question:
            prompt += (
                "\n\nUser research focus: "
                f"{context.request.custom_question.strip()}"
            )
        return prompt

    def _has_no_usable_inputs(self, context: AnalysisContext) -> bool:
        return (
            context.technical_output is None
            and context.news_sentiment_output is None
            and context.bull_case_output is None
            and context.bear_case_output is None
            and context.data_quality is None
        )

    def _company_name(self, context: AnalysisContext) -> str | None:
        if context.market_data and context.market_data.company_profile:
            return context.market_data.company_profile.name
        return None

    def _latest_close(self, context: AnalysisContext) -> str:
        if context.market_data and context.market_data.price_history:
            return self._format_float(context.market_data.price_history[-1].close)
        if context.market_data and context.market_data.quote:
            return self._format_float(context.market_data.quote.price)
        return "unavailable"

    def _latest_price_timestamp(self, context: AnalysisContext) -> str:
        if context.market_data and context.market_data.price_history:
            return self._format_datetime(context.market_data.price_history[-1].timestamp)
        if context.market_data and context.market_data.quote:
            return self._format_datetime(context.market_data.quote.as_of)
        return "unavailable"

    def _data_quality_score(self, context: AnalysisContext) -> str:
        score = self._raw_data_quality_score(context)
        if score is None:
            return "unavailable"
        return f"{score:.2f}"

    def _raw_data_quality_score(self, context: AnalysisContext) -> float | None:
        if context.data_quality and context.data_quality.score is not None:
            return context.data_quality.score
        if context.market_data and context.market_data.data_quality_score is not None:
            return context.market_data.data_quality_score
        return None

    def _price_data_status(self, context: AnalysisContext) -> str:
        if context.data_quality is not None:
            return context.data_quality.price_data_status
        return "missing"

    def _news_data_status(self, context: AnalysisContext) -> str:
        if context.data_quality is not None:
            return context.data_quality.news_data_status
        return "missing"

    def _company_profile_status(self, context: AnalysisContext) -> str:
        if context.data_quality is not None:
            return context.data_quality.fundamentals_status
        return "missing"

    def _missing_data(self, context: AnalysisContext) -> list[str]:
        if context.data_quality is not None:
            return list(context.data_quality.missing_data)
        if context.market_data is not None:
            return list(context.market_data.missing_data)
        return []

    def _provider_names(self, context: AnalysisContext) -> list[str]:
        if context.data_quality and context.data_quality.provider_names:
            return list(context.data_quality.provider_names)
        if context.market_data and context.market_data.sources:
            return [source.provider for source in context.market_data.sources]
        return []

    def _data_quality_warnings(self, context: AnalysisContext) -> list[str]:
        warnings: list[str] = []
        if context.data_quality is not None:
            warnings.extend(context.data_quality.warnings)
        if context.market_data is not None:
            warnings.extend(context.market_data.warnings)
        warnings.extend(context.warnings)
        return self._dedupe(warnings)

    def _technical_output_text(
        self,
        technical_output: TechnicalAgentOutput | None,
    ) -> str:
        if technical_output is None:
            return "Technical Research Agent output is missing."
        return json.dumps(technical_output.model_dump(mode="json"), indent=2, sort_keys=True)

    def _news_output_text(self, news_output: NewsSentimentOutput | None) -> str:
        if news_output is None:
            return "News & Sentiment Agent output is missing."
        return json.dumps(news_output.model_dump(mode="json"), indent=2, sort_keys=True)

    def _bull_case_output_text(self, bull_output: BullCaseAgentOutput | None) -> str:
        if bull_output is None:
            return "Bull Case Agent output is missing."
        return json.dumps(bull_output.model_dump(mode="json"), indent=2, sort_keys=True)

    def _bear_case_output_text(self, bear_output: BearCaseAgentOutput | None) -> str:
        if bear_output is None:
            return "Bear Case Agent output is missing."
        return json.dumps(bear_output.model_dump(mode="json"), indent=2, sort_keys=True)

    def _failed_or_missing_outputs(self, context: AnalysisContext) -> list[str]:
        missing: list[str] = []
        if context.technical_output is None:
            missing.append("Technical Research Agent output is missing.")
        if context.news_sentiment_output is None:
            missing.append("News & Sentiment Agent output is missing.")
        if context.bull_case_output is None:
            missing.append("Bull Case Agent output is missing.")
        if context.bear_case_output is None:
            missing.append("Bear Case Agent output is missing.")
        return missing

    def _input_warnings(self, context: AnalysisContext) -> list[str]:
        return self._dedupe(
            [
                *self._failed_or_missing_outputs(context),
                *self._data_quality_warnings(context),
            ]
        )

    def _data_used(self, context: AnalysisContext) -> list[str]:
        data_used: list[str] = []
        if context.technical_output is not None:
            data_used.append("technical_output")
        if context.news_sentiment_output is not None:
            data_used.append("news_sentiment_output")
        if context.bull_case_output is not None:
            data_used.append("bull_case_output")
        if context.bear_case_output is not None:
            data_used.append("bear_case_output")
        if context.data_quality is not None:
            data_used.append("data_quality")
        return data_used

    def _join_or_none(self, values: Sequence[str]) -> str:
        if not values:
            return "none"
        return "; ".join(values)

    def _format_float(self, value: float) -> str:
        return f"{value:.2f}"

    def _format_datetime(self, value: datetime) -> str:
        return value.isoformat()

    def _dedupe(self, values: Sequence[str]) -> list[str]:
        deduped: dict[str, None] = {}
        for value in values:
            stripped = value.strip()
            if stripped:
                deduped.setdefault(stripped, None)
        return list(deduped)


__all__ = [
    "RISK_REVIEW_AGENT_SYSTEM_PROMPT",
    "RISK_REVIEW_AGENT_USER_PROMPT",
    "RiskReviewAgent",
]
