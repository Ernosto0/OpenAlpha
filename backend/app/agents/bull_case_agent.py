from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from backend.app.agents.base import AgentExecutionPayload, BaseAgent
from backend.app.llm import BaseLLMProvider, LLMProviderError
from backend.app.llm.providers import OpenAIProvider
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    BullCaseAgentOutput,
    NewsSentimentOutput,
    TechnicalAgentOutput,
)


BULL_CASE_AGENT_SYSTEM_PROMPT = """
You are the Bull Case Agent for OpenAlpha, a local-first AI equity research application.

Your job is to build a reasonable bullish argument for the requested stock using only the existing Technical Research Agent output and News & Sentiment Agent output.

You are not the final decision-maker. You do not produce the final AI view, final confidence score, or investment thesis. The Thesis Agent will do that later.

Your task is to identify what could go right, what evidence supports the upside case, and what conditions would need to happen for the bullish scenario to become more credible.

Core rules:

* Use only the provided Technical Research Agent and News & Sentiment Agent outputs.
* Do not fetch external data.
* Do not calculate indicators.
* Do not invent news, catalysts, support levels, resistance levels, or company facts.
* Do not ignore weak, missing, or conflicting evidence.
* Do not provide personalized financial advice.
* Do not recommend buying, selling, holding, or investing.
* Do not use language like "buy now", "sell now", "guaranteed", "risk-free", or "you should invest".
* Use research language such as "bull case", "upside scenario", "positive setup", "potential catalyst", "technical confirmation", and "sentiment support".
* If bullish evidence is weak, say so clearly.
* If technical and news signals conflict, build only a cautious or conditional bull case.
* If there is not enough evidence for a meaningful bull case, return a weak or limited bull case rather than inventing arguments.
* Output valid JSON only.
* Do not include markdown.
* Do not include explanations outside the JSON object.

Argument guidance:

* Technical strength may include positive trend structure, improving momentum, price holding above support, breakout attempts, rising volume, or favorable risk or reward structure.
* News strength may include positive company-specific developments, improving sentiment, sector tailwinds, analyst upgrades if provided, product launches if provided, earnings strength if provided, or regulatory or legal progress if provided.
* Upside conditions should describe what would need to happen for the bullish scenario to become more convincing.
* Upside conditions should be observable and testable when possible.
* Do not turn upside conditions into advice.
* Do not say the stock "will" rise. Use conditional language such as "could", "may", "would support", or "would strengthen".

Return exactly this JSON shape:

{
"bull_case": "A concise 2-4 sentence bullish argument based only on the provided technical and news outputs.",
"main_arguments": [
"Main bullish argument 1",
"Main bullish argument 2",
"Main bullish argument 3"
],
"upside_conditions": [
"Condition that would strengthen the upside case 1",
"Condition that would strengthen the upside case 2",
"Condition that would strengthen the upside case 3"
]
}

If there is limited bullish evidence, still return the same shape, but make the bull_case cautious and include limitations inside the main_arguments.
""".strip()


BULL_CASE_AGENT_USER_PROMPT = """Build a bull case for {symbol} using the provided agent outputs.

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
* Do not invent missing facts, catalysts, or news.
* Do not provide personalized financial advice.
* Do not produce the final thesis or final AI view.
* Build the strongest reasonable bullish argument, but keep it evidence-based and conditional.
* If bullish evidence is weak or missing, clearly reflect that.
* Return valid JSON only using the required BullCaseOutput shape.
"""


class BullCaseAgent(BaseAgent[BullCaseAgentOutput]):
    name = "bull_case_agent"
    output_schema = BullCaseAgentOutput

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
            output = BullCaseAgentOutput(
                bull_case=(
                    "A meaningful bull case cannot be formed because both the "
                    "technical and news sentiment inputs are missing from the "
                    "analysis context."
                ),
                main_arguments=[
                    "Technical Research Agent output is missing.",
                    "News & Sentiment Agent output is missing.",
                    "Bullish evidence is too limited to form an evidence-based upside scenario.",
                ],
                upside_conditions=[
                    "A technical research output would be needed to assess trend and momentum support.",
                    "A news sentiment output would be needed to assess whether recent developments support the upside case.",
                ],
            )
            context.bull_case_output = output
            return AgentExecutionPayload(
                status="partial",
                provider="local",
                model="deterministic",
                output=output,
                data_used=[],
                warnings=[
                    "Bull case was generated without upstream inputs because technical and news outputs are missing."
                ],
            )

        provider = self.llm_provider or self._create_llm_provider(
            context.request.llm_provider
        )
        try:
            result = await provider.generate_json(
                messages=[
                    {"role": "system", "content": BULL_CASE_AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": self.build_user_prompt(context)},
                ],
                output_schema=BullCaseAgentOutput,
                model=context.request.llm_model,
                agent_name=self.name,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
            )
        except LLMProviderError as exc:
            if self._should_stop_on_llm_error(exc):
                raise
            output = self._fallback_output_for_llm_failure(context, str(exc))
            context.bull_case_output = output
            return AgentExecutionPayload(
                status="partial",
                provider="local",
                model="deterministic",
                output=output,
                data_used=self._data_used(context),
                warnings=self._dedupe(
                    [
                        f"Bull case used a deterministic fallback because the LLM request failed: {exc}"
                    ]
                ),
            )

        output = self.validate_output(result.content)
        if not isinstance(output, BullCaseAgentOutput):
            raise TypeError("bull case agent returned an unexpected output type")

        context.bull_case_output = output
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
    ) -> BullCaseAgentOutput:
        return BullCaseAgentOutput(
            bull_case=(
                "A full AI-generated bull case could not be produced because the "
                "configured LLM provider request failed. Any upside view should be "
                "treated as incomplete and conditional on restoring LLM access."
            ),
            main_arguments=[
                "Technical and/or news inputs may still contain constructive signals, but they were not synthesized by the Bull Case Agent.",
                "The current upside case is incomplete because the LLM-backed reasoning step failed.",
                f"LLM error: {error_message}",
            ],
            upside_conditions=[
                "LLM access is restored so the collected technical and news inputs can be synthesized.",
                "Upstream technical and sentiment outputs remain available and internally consistent.",
            ],
        )

    def build_user_prompt(self, context: AnalysisContext) -> str:
        symbol = context.request.symbol
        prompt = BULL_CASE_AGENT_USER_PROMPT.format(
            symbol=symbol,
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

    def _create_llm_provider(self, provider_name: str) -> BaseLLMProvider:
        normalized = provider_name.strip().lower()
        if normalized == "openai":
            return OpenAIProvider()
        raise ValueError(
            f"Unsupported LLM provider for bull_case_agent: {provider_name}"
        )

    def _dedupe(self, values: Sequence[str]) -> list[str]:
        deduped: dict[str, None] = {}
        for value in values:
            stripped = value.strip()
            if stripped:
                deduped.setdefault(stripped, None)
        return list(deduped)


__all__ = [
    "BULL_CASE_AGENT_SYSTEM_PROMPT",
    "BULL_CASE_AGENT_USER_PROMPT",
    "BullCaseAgent",
]
