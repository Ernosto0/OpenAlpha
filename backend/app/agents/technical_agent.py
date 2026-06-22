from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from backend.app.agents.base import AgentExecutionPayload, BaseAgent
from backend.app.llm import BaseLLMProvider, LLMProviderError
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    IndicatorBundle,
    TechnicalAgentOutput,
)


TECHNICAL_SYSTEM_PROMPT = """
You are the Technical Research Agent for OpenAlpha, a local-first AI equity research application.

Your job is to interpret already-calculated technical indicators and price structure. You must not fetch data, calculate indicators, invent missing values, or give personalized financial advice.

You receive structured technical data from the Data Collector through AnalysisContext. The indicators, support/resistance levels, volatility values, and data quality score were calculated deterministically by Python code before this step.

Your task is to produce a concise technical research view using only the provided data.

Core rules:

* Interpret the provided technical data only.
* Do not calculate new indicators.
* Do not invent missing indicator values.
* Do not make buy, sell, hold, or position-sizing recommendations.
* Do not use language like "buy now", "sell now", "guaranteed", "risk-free", or "you should invest".
* Use research language such as "technical view", "momentum", "trend", "risk", "support", "resistance", "invalidation", and "data limitation".
* If data is missing, stale, inconsistent, or low quality, lower confidence and add warnings.
* If signals conflict, explicitly say they are mixed.
* If there is not enough technical evidence, return a neutral or insufficient_data view.
* Output valid JSON only.
* Do not include markdown.
* Do not include explanations outside the JSON object.

Allowed values for view:

* bullish
* slightly_bullish
* neutral
* slightly_bearish
* bearish
* insufficient_data

Confidence rules:

* confidence must be a number between 0 and 1.
* Use 0.75-0.90 only when indicators are consistent, recent, and data quality is high.
* Use 0.50-0.74 when the technical picture is reasonably clear but not perfect.
* Use 0.25-0.49 when signals are mixed, weak, stale, or data quality is low.
* Use 0.00-0.24 when technical data is mostly missing or unreliable.

Interpretation guidance:

* Trend:
  * Price above major moving averages may indicate positive trend structure.
  * Price below major moving averages may indicate negative trend structure.
  * Moving average compression or crossovers may indicate transition or uncertainty.
* Momentum:
  * RSI above typical overbought levels may indicate stretched upside momentum.
  * RSI below typical oversold levels may indicate stretched downside momentum.
  * MACD direction and histogram should be interpreted as momentum confirmation or divergence.
* Volatility:
  * Wide Bollinger Bands, high ATR, or large recent ranges suggest higher uncertainty.
  * Low volatility can suggest consolidation, but do not assume breakout direction without evidence.
* Support and resistance:
  * Use only the provided support and resistance levels.
  * Mention nearby levels that matter for the current price.
  * Do not invent precise levels.
* Volume:
  * Rising volume with price movement may strengthen the signal.
  * Weak volume may reduce confidence.
* Data quality:
  * Always consider data_quality_score and warnings from the Data Collector.
  * If price data is missing, stale, or very short, the output should be cautious.

Return exactly this JSON shape:

{
"view": "bullish | slightly_bullish | neutral | slightly_bearish | bearish | insufficient_data",
"confidence": 0.0,
"summary": "A concise technical summary in 2-4 sentences.",
"key_signals": [
"Signal 1",
"Signal 2",
"Signal 3"
],
"support_levels": [
{
"price": 0.0,
"reason": "Why this support level matters.",
"strength": "weak | moderate | strong"
}
],
"resistance_levels": [
{
"price": 0.0,
"reason": "Why this resistance level matters.",
"strength": "weak | moderate | strong"
}
],
"warnings": [
"Warning or limitation 1"
]
}

If support or resistance levels are unavailable, return an empty array for that field.

If there are no warnings, return an empty warnings array.
""".strip()


class TechnicalAgent(BaseAgent[TechnicalAgentOutput]):
    name = "technical_agent"
    output_schema = TechnicalAgentOutput

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
        if context.indicators is None:
            output = TechnicalAgentOutput(
                view="insufficient_data",
                confidence=0,
                summary=(
                    "Technical view is unavailable because no technical "
                    "indicator bundle is present in the analysis context."
                ),
                warnings=["Technical indicators are missing from context."],
            )
            context.technical_output = output
            return AgentExecutionPayload(
                status="partial",
                provider="local",
                model="deterministic",
                output=output,
                data_used=[],
                warnings=output.warnings,
            )

        provider = self.llm_provider or self._create_llm_provider(
            context.request.llm_provider
        )
        try:
            result = await provider.generate_json(
                messages=[
                    {"role": "system", "content": TECHNICAL_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": self.build_user_prompt(context),
                    },
                ],
                output_schema=TechnicalAgentOutput,
                model=context.request.llm_model,
                agent_name=self.name,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
            )
        except LLMProviderError as exc:
            if self._should_stop_on_llm_error(exc):
                raise
            output = self._fallback_output_for_llm_failure(context, str(exc))
            context.technical_output = output
            return AgentExecutionPayload(
                status="partial",
                provider="local",
                model="deterministic",
                output=output,
                data_used=["technical_indicators"],
                warnings=output.warnings,
            )

        output = self.validate_output(result.content)
        if not isinstance(output, TechnicalAgentOutput):
            raise TypeError("technical agent returned an unexpected output type")

        context.technical_output = output
        warnings = self._dedupe([*result.warnings, *output.warnings])

        return AgentExecutionPayload(
            status="completed",
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            output=output,
            data_used=["technical_indicators"],
            warnings=warnings,
            parsing_errors=result.parsing_errors,
        )

    def _fallback_output_for_llm_failure(
        self,
        context: AnalysisContext,
        error_message: str,
    ) -> TechnicalAgentOutput:
        warnings = self._dedupe(
            [
                "Technical analysis used a deterministic fallback because the LLM request failed.",
                f"LLM error: {error_message}",
                *self._data_quality_warnings(context),
            ]
        )
        return TechnicalAgentOutput(
            view="insufficient_data",
            confidence=0.15,
            summary=(
                "Technical indicators were available, but the AI interpretation step "
                "could not be completed because the configured LLM provider request failed."
            ),
            key_signals=[
                "A deterministic fallback was used instead of full LLM-based technical interpretation.",
                f"Latest close price: {self._latest_close(context)}.",
                f"Latest price timestamp: {self._latest_price_timestamp(context)}.",
            ],
            warnings=warnings,
        )

    def build_user_prompt(self, context: AnalysisContext) -> str:
        indicators = context.indicators
        if indicators is None:
            raise ValueError("indicators are required to build the technical prompt")

        data_quality_warnings = self._data_quality_warnings(context)
        payload = self._indicator_prompt_payload(
            indicators,
            data_quality_score=self._data_quality_score(context),
            data_quality_warnings=data_quality_warnings,
        )
        symbol = indicators.symbol
        company_name = self._company_name(context) or "Unknown"
        market = context.request.market
        horizon = context.request.horizon
        price_interval = self._price_interval(horizon)
        lookback_period = self._lookback_period(context)
        latest_close = self._latest_close(context)
        latest_price_timestamp = self._latest_price_timestamp(context)
        prompt = (
            f"""Analyze the following technical data for {symbol}.

Context:
- Symbol: {symbol}
- Company name: {company_name}
- Market: {market}
- Time horizon: {horizon}
- Price interval: {price_interval}
- Lookback period: {lookback_period}
- Latest close price: {latest_close}
- Latest price timestamp: {latest_price_timestamp}
- Data quality score: {payload["data_quality_score"]}
- Data quality warnings: {self._join_or_none(data_quality_warnings)}

Trend indicators:
{self._moving_average_summary(indicators, context)}

Momentum indicators:
{self._rsi_summary(indicators)}
{self._macd_summary(indicators)}

Volatility indicators:
{self._bollinger_bands_summary(indicators)}
{self._atr_summary(indicators)}

Volume indicators:
{self._volume_trend_summary(indicators)}

Support and resistance:
- Support levels: {self._numeric_levels_summary(indicators.support_levels)}
- Resistance levels: {self._numeric_levels_summary(indicators.resistance_levels)}

Recent price summary:
{self._recent_price_summary(context)}

Important constraints:
- Use only the data above.
- Do not fetch external data.
- Do not calculate new indicators.
- Do not provide personalized financial advice.
- Return valid JSON only using the required TechnicalAgentOutput shape.

Structured technical payload:
{json.dumps(payload, indent=2, sort_keys=True)}"""
        )
        if context.request.custom_question:
            prompt += (
                "\n\nUser research focus: "
                f"{context.request.custom_question.strip()}"
            )
        return prompt

    def _indicator_prompt_payload(
        self,
        indicators: IndicatorBundle,
        *,
        data_quality_score: float | None = None,
        data_quality_warnings: Sequence[str] = (),
    ) -> dict[str, Any]:
        return {
            "symbol": indicators.symbol,
            "horizon": indicators.horizon,
            "generated_at": indicators.generated_at.isoformat(),
            "rsi": indicators.rsi.model_dump(mode="json")
            if indicators.rsi is not None
            else None,
            "macd": indicators.macd.model_dump(mode="json")
            if indicators.macd is not None
            else None,
            "moving_averages": indicators.moving_averages,
            "bollinger_bands": indicators.bollinger_bands.model_dump(mode="json")
            if indicators.bollinger_bands is not None
            else None,
            "atr": indicators.atr,
            "volume_trend": indicators.volume_trend.model_dump(mode="json")
            if indicators.volume_trend is not None
            else None,
            "volatility": indicators.volatility,
            "support_levels": indicators.support_levels,
            "resistance_levels": indicators.resistance_levels,
            "signals": [
                signal.model_dump(mode="json") for signal in indicators.signals
            ],
            "indicator_warnings": indicators.warnings,
            "data_quality_score": data_quality_score,
            "data_quality_warnings": list(data_quality_warnings),
        }

    def _company_name(self, context: AnalysisContext) -> str | None:
        if context.market_data and context.market_data.company_profile:
            return context.market_data.company_profile.name
        return None

    def _price_interval(self, horizon: str) -> str:
        return {
            "1w": "daily",
            "1m": "daily",
            "3m": "daily",
            "6m": "daily",
            "1y": "weekly",
        }.get(horizon, "unknown")

    def _lookback_period(self, context: AnalysisContext) -> str:
        if context.market_data and context.market_data.price_history:
            first_bar = context.market_data.price_history[0]
            last_bar = context.market_data.price_history[-1]
            return (
                f"{first_bar.timestamp.date().isoformat()} to "
                f"{last_bar.timestamp.date().isoformat()}"
            )
        return "unavailable"

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

    def _moving_average_summary(
        self,
        indicators: IndicatorBundle,
        context: AnalysisContext,
    ) -> str:
        if not indicators.moving_averages:
            return "- Moving averages unavailable."

        latest_close = None
        if context.market_data and context.market_data.price_history:
            latest_close = context.market_data.price_history[-1].close
        parts = []
        for period, value in sorted(
            indicators.moving_averages.items(),
            key=lambda item: int(item[0]),
        ):
            relation = ""
            if latest_close is not None:
                relation = (
                    " (price above)"
                    if latest_close > value
                    else " (price below)"
                    if latest_close < value
                    else " (price at)"
                )
            parts.append(f"SMA {period}: {self._format_float(value)}{relation}")
        return "- " + "; ".join(parts)

    def _rsi_summary(self, indicators: IndicatorBundle) -> str:
        if indicators.rsi is None or indicators.rsi.value is None:
            return "- RSI unavailable."
        explanation = indicators.rsi.explanation or "No explanation provided."
        return (
            f"- RSI: {self._format_float(indicators.rsi.value)}; "
            f"signal={indicators.rsi.signal}; {explanation}"
        )

    def _macd_summary(self, indicators: IndicatorBundle) -> str:
        if indicators.macd is None or indicators.macd.macd is None:
            return "- MACD unavailable."
        return (
            f"- MACD: {self._format_optional_float(indicators.macd.macd)}; "
            f"signal line={self._format_optional_float(indicators.macd.signal)}; "
            f"histogram={self._format_optional_float(indicators.macd.histogram)}"
        )

    def _bollinger_bands_summary(self, indicators: IndicatorBundle) -> str:
        if indicators.bollinger_bands is None:
            return "- Bollinger Bands unavailable."
        bands = indicators.bollinger_bands
        return (
            f"- Bollinger Bands: upper={self._format_optional_float(bands.upper)}, "
            f"middle={self._format_optional_float(bands.middle)}, "
            f"lower={self._format_optional_float(bands.lower)}"
        )

    def _atr_summary(self, indicators: IndicatorBundle) -> str:
        if indicators.atr is None:
            return "- ATR unavailable."
        return f"- ATR: {self._format_float(indicators.atr)}"

    def _volume_trend_summary(self, indicators: IndicatorBundle) -> str:
        if indicators.volume_trend is None:
            return "- Volume trend unavailable."
        volume = indicators.volume_trend
        return (
            f"- Volume trend: direction={volume.direction}; "
            f"short average={self._format_optional_float(volume.short_average)}; "
            f"long average={self._format_optional_float(volume.long_average)}; "
            f"ratio={self._format_optional_float(volume.ratio)}"
        )

    def _numeric_levels_summary(self, levels: Sequence[float]) -> str:
        if not levels:
            return "none"
        return ", ".join(self._format_float(level) for level in levels)

    def _recent_price_summary(self, context: AnalysisContext) -> str:
        if not context.market_data or not context.market_data.price_history:
            return "- Recent price history unavailable."

        bars = context.market_data.price_history[-5:]
        parts = []
        for bar in bars:
            parts.append(
                (
                    f"{bar.timestamp.date().isoformat()}: "
                    f"close={self._format_float(bar.close)}"
                )
            )
        return "- " + "; ".join(parts)

    def _data_quality_warnings(self, context: AnalysisContext) -> list[str]:
        warnings: list[str] = []
        if context.data_quality:
            warnings.extend(context.data_quality.warnings)
        if context.market_data:
            warnings.extend(context.market_data.warnings)
        warnings.extend(context.warnings)
        return self._dedupe(warnings)

    def _data_quality_score(self, context: AnalysisContext) -> float | None:
        if context.data_quality and context.data_quality.score is not None:
            return context.data_quality.score
        if context.market_data and context.market_data.data_quality_score is not None:
            return context.market_data.data_quality_score
        return None

    def _join_or_none(self, values: Sequence[str]) -> str:
        if not values:
            return "none"
        return "; ".join(values)

    def _format_float(self, value: float) -> str:
        return f"{value:.2f}"

    def _format_optional_float(self, value: float | None) -> str:
        if value is None:
            return "unavailable"
        return self._format_float(value)

    def _format_datetime(self, value: datetime) -> str:
        return value.isoformat()

    def _dedupe(self, values: Sequence[str]) -> list[str]:
        deduped: dict[str, None] = {}
        for value in values:
            stripped = value.strip()
            if stripped:
                deduped.setdefault(stripped, None)
        return list(deduped)


TechnicalResearchAgent = TechnicalAgent


__all__ = ["TECHNICAL_SYSTEM_PROMPT", "TechnicalAgent", "TechnicalResearchAgent"]
