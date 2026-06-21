from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from backend.app.agents.base import AgentExecutionPayload, BaseAgent
from backend.app.llm import BaseLLMProvider
from backend.app.llm.providers import OpenAIProvider
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    BearCaseAgentOutput,
    BullCaseAgentOutput,
    DataCollectorOutput,
    DataQualitySummary,
    NewsSentimentOutput,
    RiskReviewAgentOutput,
    TechnicalAgentOutput,
    ThesisAgentOutput,
)


THESIS_AGENT_SYSTEM_PROMPT = """
You are the Thesis Agent for OpenAlpha, a local-first AI equity research application.

Your job is to synthesize all previous agent outputs into a final AI research view for the requested stock.

You must read the Data Collector output, Technical Research Agent output, News & Sentiment Agent output, Bull Case Agent output, Bear Case Agent output, and Risk Review Agent output.

You are not a financial advisor. You must not provide personalized financial advice, investment advice, or a recommendation to buy or sell any security.

Your task is to produce a balanced research thesis, including the base case, bull case summary, bear case summary, confidence score, and what-to-watch list.

Core rules:

* Use only the provided AnalysisContext and previous agent outputs.
* Do not fetch external data.
* Do not calculate new indicators.
* Do not invent company facts, news, catalysts, risks, prices, or financial data.
* Do not ignore failed or missing agent outputs.
* Do not hide uncertainty or data limitations.
* Do not recommend buying, selling, holding, shorting, or investing.
* Do not use language like “buy now”, “sell now”, “guaranteed”, “risk-free”, “you should invest”, or “this is a sure thing”.
* Use research language such as “AI view”, “investment thesis”, “base case”, “bull case”, “bear case”, “risk level”, “confidence”, “what to watch”, and “data limitation”.
* If evidence is mixed, say so clearly.
* If data quality is low, confidence must be reduced.
* If critical data is missing, return an insufficient_data or neutral view.
* Output valid JSON only.
* Do not include markdown.
* Do not include explanations outside the JSON object.

Allowed values for overall_view:

* bullish
* slightly_bullish
* neutral
* slightly_bearish
* bearish
* insufficient_data

Confidence rules:

* confidence must be a number between 0 and 1.
* Start from the strength and consistency of technical, news, bull, and bear evidence.
* Apply the Risk Review Agent confidence_adjustment.
* Use 0.75–0.90 only when evidence is strong, consistent, recent, and data quality is high.
* Use 0.50–0.74 when the thesis is reasonable but has meaningful uncertainty.
* Use 0.25–0.49 when evidence is mixed, weak, incomplete, or data quality is low.
* Use 0.00–0.24 when the analysis is mostly unreliable or insufficient.
* Never use confidence above 0.90 in V1.
* Do not assign high confidence when the Risk Review Agent reports high, very_high, or insufficient_data risk.

Synthesis guidance:

* The base_case should describe the most balanced and likely interpretation of the provided evidence.
* The bull_case_summary should summarize the strongest reasonable upside argument.
* The bear_case_summary should summarize the strongest reasonable downside argument.
* The thesis should explain the final AI research view in a balanced way.
* The what_to_watch list should include observable items that could confirm, weaken, or change the thesis.
* If technical and news evidence conflict, the thesis should reflect that conflict instead of forcing a strong view.
* If news is missing but technical data is usable, say that the thesis is mostly technical and confidence is limited.
* If price data is weak or missing, the thesis should be insufficient_data or highly cautious.
* If prior agents failed, mention the limitation in the thesis and lower confidence.

Return exactly this JSON shape:

{
"overall_view": "bullish | slightly_bullish | neutral | slightly_bearish | bearish | insufficient_data",
"confidence": 0.0,
"horizon": "The time horizon used for this thesis.",
"thesis": "A concise 3-5 sentence final AI research thesis based on all previous outputs.",
"base_case": "A concise summary of the most balanced expected scenario.",
"bull_case_summary": "A concise summary of the upside scenario.",
"bear_case_summary": "A concise summary of the downside scenario.",
"what_to_watch": [
"Observable item to watch 1",
"Observable item to watch 2",
"Observable item to watch 3"
]
}

If there is insufficient usable data, return:

{
"overall_view": "insufficient_data",
"confidence": 0.1,
"horizon": "The requested time horizon.",
"thesis": "The available data is insufficient to produce a reliable AI research thesis. The analysis should be treated as incomplete because key agent outputs or data sources were missing, failed, stale, or low quality.",
"base_case": "No reliable base case can be formed from the provided data.",
"bull_case_summary": "No reliable bull case can be formed from the provided data.",
"bear_case_summary": "No reliable bear case can be formed from the provided data.",
"what_to_watch": [
"Whether usable price data becomes available.",
"Whether usable company-specific news becomes available.",
"Whether failed or missing agent outputs can be regenerated."
]
}

""".strip()


THESIS_AGENT_USER_PROMPT = """Create a final AI research thesis for {symbol} using all previous agent outputs.

Context:

* Symbol: {symbol}
* Company name: {company_name}
* Market: {market}
* Requested horizon: {horizon}
* Analysis depth: {analysis_depth}
* Latest close price: {latest_close}
* Latest price timestamp: {latest_price_timestamp}

Data Collector output:
{data_collector_output}

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

Risk Review Agent output:
{risk_review_agent_output}

Failed or missing agent outputs:
{failed_agent_outputs}

Important constraints:

* Use only the provided context and previous agent outputs.
* Do not fetch external data.
* Do not calculate new indicators.
* Do not invent missing facts, catalysts, risks, prices, or news.
* Do not provide personalized financial advice.
* Do not recommend buying, selling, holding, shorting, or investing.
* Produce the final AI research view.
* Apply the Risk Review Agent confidence_adjustment when deciding final confidence.
* Lower confidence when data quality is weak, evidence is mixed, or agent outputs are missing.
* Return valid JSON only using the required ThesisOutput shape.
"""


class ThesisAgent(BaseAgent[ThesisAgentOutput]):
    name = "thesis_agent"
    output_schema = ThesisAgentOutput

    def __init__(
        self,
        *,
        llm_provider: BaseLLMProvider | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1100,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.llm_provider = llm_provider
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    async def execute(self, context: AnalysisContext) -> AgentExecutionPayload:
        if self._has_no_usable_inputs(context):
            output = ThesisAgentOutput(
                overall_view="insufficient_data",
                confidence=0.1,
                horizon=context.request.horizon,
                thesis=(
                    "The available data is insufficient to produce a reliable AI "
                    "research thesis. The analysis should be treated as incomplete "
                    "because key agent outputs or data sources were missing, failed, "
                    "stale, or low quality."
                ),
                base_case="No reliable base case can be formed from the provided data.",
                bull_case_summary=(
                    "No reliable bull case can be formed from the provided data."
                ),
                bear_case_summary=(
                    "No reliable bear case can be formed from the provided data."
                ),
                what_to_watch=[
                    "Whether usable price data becomes available.",
                    "Whether usable company-specific news becomes available.",
                    "Whether failed or missing agent outputs can be regenerated.",
                ],
            )
            context.thesis_output = output
            return AgentExecutionPayload(
                status="partial",
                provider="local",
                model="deterministic",
                output=output,
                data_used=[],
                warnings=["Thesis was generated without usable upstream inputs."],
            )

        provider = self.llm_provider or self._create_llm_provider(
            context.request.llm_provider
        )
        result = await provider.generate_json(
            messages=[
                {"role": "system", "content": THESIS_AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": self.build_user_prompt(context)},
            ],
            output_schema=ThesisAgentOutput,
            model=context.request.llm_model,
            agent_name=self.name,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )

        output = self.validate_output(result.content)
        if not isinstance(output, ThesisAgentOutput):
            raise TypeError("thesis agent returned an unexpected output type")

        context.thesis_output = output
        warnings = self._dedupe([*result.warnings, *self._input_warnings(context)])

        return AgentExecutionPayload(
            status="completed",
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            output=output,
            data_used=self._data_used(context),
            warnings=warnings,
            parsing_errors=result.parsing_errors,
        )

    def build_user_prompt(self, context: AnalysisContext) -> str:
        prompt = THESIS_AGENT_USER_PROMPT.format(
            symbol=context.request.symbol,
            company_name=self._company_name(context) or "Unknown",
            market=context.request.market,
            horizon=context.request.horizon,
            analysis_depth=context.request.depth,
            latest_close=self._latest_close(context),
            latest_price_timestamp=self._latest_price_timestamp(context),
            data_collector_output=self._data_collector_output_text(context),
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
            risk_review_agent_output=self._risk_review_output_text(
                context.risk_review_output
            ),
            failed_agent_outputs=self._join_or_none(self._failed_or_missing_outputs(context)),
        )

        structured_payload = {
            "data_collector_output": self._data_collector_output_payload(context),
            "technical_output": self._model_dump_or_none(context.technical_output),
            "news_sentiment_output": self._model_dump_or_none(
                context.news_sentiment_output
            ),
            "bull_case_output": self._model_dump_or_none(context.bull_case_output),
            "bear_case_output": self._model_dump_or_none(context.bear_case_output),
            "risk_review_output": self._model_dump_or_none(context.risk_review_output),
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
            context.market_data is None
            and context.data_quality is None
            and context.technical_output is None
            and context.news_sentiment_output is None
            and context.bull_case_output is None
            and context.bear_case_output is None
            and context.risk_review_output is None
        )

    def _data_collector_output_payload(
        self,
        context: AnalysisContext,
    ) -> dict[str, Any] | None:
        if context.market_data is None and context.data_quality is None:
            return None

        return DataCollectorOutput(
            market_data=context.market_data
            if context.market_data is not None
            else self._fallback_market_data_bundle(context),
            data_quality=context.data_quality
            if context.data_quality is not None
            else DataQualitySummary(),
        ).model_dump(mode="json")

    def _data_collector_output_text(self, context: AnalysisContext) -> str:
        payload = self._data_collector_output_payload(context)
        if payload is None:
            return "Data Collector output is missing."
        return json.dumps(payload, indent=2, sort_keys=True)

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

    def _risk_review_output_text(
        self,
        risk_output: RiskReviewAgentOutput | None,
    ) -> str:
        if risk_output is None:
            return "Risk Review Agent output is missing."
        return json.dumps(risk_output.model_dump(mode="json"), indent=2, sort_keys=True)

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

    def _failed_or_missing_outputs(self, context: AnalysisContext) -> list[str]:
        missing: list[str] = []
        if context.market_data is None and context.data_quality is None:
            missing.append("Data Collector output is missing.")
        if context.technical_output is None:
            missing.append("Technical Research Agent output is missing.")
        if context.news_sentiment_output is None:
            missing.append("News & Sentiment Agent output is missing.")
        if context.bull_case_output is None:
            missing.append("Bull Case Agent output is missing.")
        if context.bear_case_output is None:
            missing.append("Bear Case Agent output is missing.")
        if context.risk_review_output is None:
            missing.append("Risk Review Agent output is missing.")
        for agent_result in context.agent_results:
            if agent_result.status == "failed":
                missing.append(
                    f"{agent_result.agent_name} failed: "
                    f"{agent_result.error_message or 'unknown error'}"
                )
        return self._dedupe(missing)

    def _input_warnings(self, context: AnalysisContext) -> list[str]:
        return self._dedupe(
            [
                *self._failed_or_missing_outputs(context),
                *self._data_quality_warnings(context),
            ]
        )

    def _data_used(self, context: AnalysisContext) -> list[str]:
        data_used: list[str] = []
        if context.market_data is not None:
            data_used.append("market_data")
        if context.data_quality is not None:
            data_used.append("data_quality")
        if context.technical_output is not None:
            data_used.append("technical_output")
        if context.news_sentiment_output is not None:
            data_used.append("news_sentiment_output")
        if context.bull_case_output is not None:
            data_used.append("bull_case_output")
        if context.bear_case_output is not None:
            data_used.append("bear_case_output")
        if context.risk_review_output is not None:
            data_used.append("risk_review_output")
        return data_used

    def _fallback_market_data_bundle(self, context: AnalysisContext):
        from backend.app.orchestrator.schemas import MarketDataBundle

        return MarketDataBundle(
            symbol=context.request.symbol,
            market=context.request.market,
        )

    def _model_dump_or_none(self, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        return value.model_dump(mode="json")

    def _join_or_none(self, values: Sequence[str]) -> str:
        if not values:
            return "none"
        return "; ".join(values)

    def _format_float(self, value: float) -> str:
        return f"{value:.2f}"

    def _format_datetime(self, value: datetime) -> str:
        return value.isoformat()

    def _create_llm_provider(self, provider_name: str) -> BaseLLMProvider:
        normalized = provider_name.strip().lower()
        if normalized == "openai":
            return OpenAIProvider()
        raise ValueError(f"Unsupported LLM provider for thesis_agent: {provider_name}")

    def _dedupe(self, values: Sequence[str]) -> list[str]:
        deduped: dict[str, None] = {}
        for value in values:
            stripped = value.strip()
            if stripped:
                deduped.setdefault(stripped, None)
        return list(deduped)


__all__ = [
    "THESIS_AGENT_SYSTEM_PROMPT",
    "THESIS_AGENT_USER_PROMPT",
    "ThesisAgent",
]
