from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from backend.app.agents.base import AgentExecutionPayload, BaseAgent
from backend.app.llm import BaseLLMProvider, LLMProviderError
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    BearCaseAgentOutput,
    NewsSentimentOutput,
    TechnicalAgentOutput,
)


BEAR_CASE_AGENT_SYSTEM_PROMPT = """You are the Bear Case Agent for OpenAlpha, a local-first AI equity research application.

Your job is to build a reasonable bearish argument for the requested stock using only the existing Technical Research Agent output and News & Sentiment Agent output.

You are not the final decision-maker. You do not produce the final AI view, final confidence score, final risk level, or investment thesis. The Risk Review Agent and Thesis Agent will do that later.

Your task is to identify what could go wrong, what evidence supports the downside case, and what conditions would make the bearish scenario more credible.

Core rules:

* Use only the provided Technical Research Agent and News & Sentiment Agent outputs.
* Do not fetch external data.
* Do not calculate indicators.
* Do not invent news, risks, lawsuits, earnings issues, support breaks, resistance levels, or company facts.
* Do not exaggerate risks beyond the evidence provided.
* Do not ignore positive or conflicting evidence.
* Do not provide personalized financial advice.
* Do not recommend buying, selling, holding, shorting, or investing.
* Do not use language like "sell now", "short this", "guaranteed downside", "risk-free", or "you should avoid".
* Use research language such as "bear case", "downside scenario", "negative setup", "risk factor", "technical weakness", "sentiment pressure", and "downside condition".
* If bearish evidence is weak, say so clearly.
* If technical and news signals conflict, build only a cautious or conditional bear case.
* If there is not enough evidence for a meaningful bear case, return a weak/limited bear case rather than inventing risks.
* Output valid JSON only.
* Do not include markdown.
* Do not include explanations outside the JSON object.

Risk interpretation guidance:

* Technical weakness may include negative trend structure, weakening momentum, price failing near resistance, price breaking support, bearish MACD behavior, elevated volatility, or weak volume confirmation.
* News weakness may include negative company-specific developments, worsening sentiment, sector headwinds, analyst downgrades if provided, product delays if provided, earnings weakness if provided, legal/regulatory risk if provided, or management/company-specific concerns if provided.
* Downside conditions should describe what would need to happen for the bearish scenario to become more convincing.
* Downside conditions should be observable and testable when possible.
* Do not turn downside conditions into advice.
* Do not say the stock "will" fall. Use conditional language such as "could", "may", "would pressure", or "would weaken the setup".

Return exactly this JSON shape:

{
"bear_case": "A concise 2-4 sentence bearish argument based only on the provided technical and news outputs.",
"main_risks": [
"Main bearish risk 1",
"Main bearish risk 2",
"Main bearish risk 3"
],
"downside_conditions": [
"Condition that would strengthen the downside case 1",
"Condition that would strengthen the downside case 2",
"Condition that would strengthen the downside case 3"
]
}

If there is limited bearish evidence, still return the same shape, but make the bear_case cautious and include limitations inside the main_risks.
""".strip()

BEAR_CASE_AGENT_USER_PROMPT = """Build a bear case for {symbol} using the provided agent outputs.

Context:

* Symbol: {symbol}
* Company name: {company_name}
* Market: {market}
* Time horizon: {horizon}
* Analysis depth: {analysis_depth}
* Latest close price: {latest_close}
* Data quality score: {data_quality_score}
* Data quality warnings: {data_quality_warnings}

Technical Research Agent output:
{technical_agent_output}

News & Sentiment Agent output:
{news_sentiment_agent_output}

Important constraints:

* Use only the Technical Research Agent and News & Sentiment Agent outputs above.
* Do not fetch external data.
* Do not calculate new indicators.
* Do not invent missing facts, risks, negative catalysts, or news.
* Do not provide personalized financial advice.
* Do not produce the final thesis, final AI view, or final risk level.
* Build the strongest reasonable bearish argument, but keep it evidence-based and conditional.
* If bearish evidence is weak or missing, clearly reflect that.
* Return valid JSON only using the required BearCaseOutput shape.
"""


class BearCaseAgent(BaseAgent[BearCaseAgentOutput]):
    name = "bear_case_agent"
    output_schema = BearCaseAgentOutput

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
        technical_output = context.technical_output
        news_output = context.news_sentiment_output

        if technical_output is None and news_output is None:
            output = BearCaseAgentOutput(
                bear_case=(
                    "A meaningful bear case cannot be formed because both the "
                    "technical and news sentiment inputs are missing from the "
                    "analysis context."
                ),
                main_risks=[
                    "Technical Research Agent output is missing.",
                    "News & Sentiment Agent output is missing.",
                    "Bearish evidence is too limited to form an evidence-based downside scenario.",
                ],
                downside_conditions=[
                    "A technical research output would be needed to assess whether price action and momentum show technical weakness.",
                    "A news sentiment output would be needed to assess whether recent developments add credible downside pressure.",
                ],
            )
            context.bear_case_output = output
            return AgentExecutionPayload(
                status="partial",
                provider="local",
                model="deterministic",
                output=output,
                data_used=[],
                warnings=[
                    "Bear case was generated without upstream inputs because technical and news outputs are missing."
                ],
            )

        provider = self.llm_provider or self._create_llm_provider(
            context.request.llm_provider
        )
        try:
            result = await provider.generate_json(
                messages=[
                    {"role": "system", "content": BEAR_CASE_AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": self.build_user_prompt(context)},
                ],
                output_schema=BearCaseAgentOutput,
                model=context.request.llm_model,
                agent_name=self.name,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
            )
        except LLMProviderError as exc:
            if self._should_stop_on_llm_error(exc):
                raise
            output = self._fallback_output_for_llm_failure(context, str(exc))
            context.bear_case_output = output
            return AgentExecutionPayload(
                status="partial",
                provider="local",
                model="deterministic",
                output=output,
                data_used=self._data_used(context),
                warnings=self._dedupe(
                    [
                        f"Bear case used a deterministic fallback because the LLM request failed: {exc}"
                    ]
                ),
            )

        output = self.validate_output(result.content)
        if not isinstance(output, BearCaseAgentOutput):
            raise TypeError("bear case agent returned an unexpected output type")

        context.bear_case_output = output
        warnings = self._dedupe(
            [
                *result.warnings,
                *self._input_warnings(context),
            ]
        )

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

    def _fallback_output_for_llm_failure(
        self,
        context: AnalysisContext,
        error_message: str,
    ) -> BearCaseAgentOutput:
        return BearCaseAgentOutput(
            bear_case=(
                "A full AI-generated bear case could not be produced because the "
                "configured LLM provider request failed. Any downside view should be "
                "treated as incomplete and conditional on restoring LLM access."
            ),
            main_risks=[
                "Technical and/or news inputs may still contain downside signals, but they were not synthesized by the Bear Case Agent.",
                "The current downside case is incomplete because the LLM-backed reasoning step failed.",
                f"LLM error: {error_message}",
            ],
            downside_conditions=[
                "LLM access is restored so the collected technical and news inputs can be synthesized.",
                "Upstream technical and sentiment outputs remain available and internally consistent.",
            ],
        )

    def build_user_prompt(self, context: AnalysisContext) -> str:
        prompt = BEAR_CASE_AGENT_USER_PROMPT.format(
            symbol=context.request.symbol,
            company_name=self._company_name(context) or "Unknown",
            market=context.request.market,
            horizon=context.request.horizon,
            analysis_depth=context.request.depth,
            latest_close=self._latest_close(context),
            data_quality_score=self._data_quality_score(context),
            data_quality_warnings=self._join_or_none(self._data_quality_warnings(context)),
            technical_agent_output=self._technical_output_text(context.technical_output),
            news_sentiment_agent_output=self._news_output_text(
                context.news_sentiment_output
            ),
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
            "data_quality_score": self._raw_data_quality_score(context),
            "data_quality_warnings": self._data_quality_warnings(context),
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

    def _data_quality_warnings(self, context: AnalysisContext) -> list[str]:
        warnings: list[str] = []
        if context.data_quality:
            warnings.extend(context.data_quality.warnings)
        if context.market_data:
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

    def _input_warnings(self, context: AnalysisContext) -> list[str]:
        warnings: list[str] = []
        if context.technical_output is None:
            warnings.append("Technical Research Agent output is missing.")
        if context.news_sentiment_output is None:
            warnings.append("News & Sentiment Agent output is missing.")
        warnings.extend(self._data_quality_warnings(context))
        return self._dedupe(warnings)

    def _data_used(self, context: AnalysisContext) -> list[str]:
        data_used: list[str] = []
        if context.technical_output is not None:
            data_used.append("technical_output")
        if context.news_sentiment_output is not None:
            data_used.append("news_sentiment_output")
        return data_used

    def _join_or_none(self, values: Sequence[str]) -> str:
        if not values:
            return "none"
        return "; ".join(values)

    def _format_float(self, value: float) -> str:
        return f"{value:.2f}"

    def _dedupe(self, values: Sequence[str]) -> list[str]:
        deduped: dict[str, None] = {}
        for value in values:
            stripped = value.strip()
            if stripped:
                deduped.setdefault(stripped, None)
        return list(deduped)


__all__ = [
    "BEAR_CASE_AGENT_SYSTEM_PROMPT",
    "BEAR_CASE_AGENT_USER_PROMPT",
    "BearCaseAgent",
]
