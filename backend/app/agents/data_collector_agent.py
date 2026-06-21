from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from backend.app.agents.base import AgentExecutionPayload, BaseAgent
from backend.app.marketdata.base import (
    CompanyFactsResult,
    MarketDataProvider,
    PriceHistoryResult,
    get_default_market_data_provider,
)
from backend.app.marketdata.providers.sec_provider import SECProvider
from backend.app.news.base import NewsProviderResult, get_news_service
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    DataCollectorOutput,
    DataQualitySummary,
    DataSource,
    DataStatus,
    MarketDataBundle,
    NewsItem,
    PriceBar,
    normalize_symbol_value,
)
from backend.app.technicalindicators import calculate_indicators


class NewsFetcher(Protocol):
    async def get_news(
        self,
        symbol: str,
        *,
        query: str | None = None,
        limit: int = 20,
        language: str = "en",
    ) -> NewsProviderResult:
        ...


class DataCollectorAgent(BaseAgent[DataCollectorOutput]):
    name = "data_collector"
    output_schema = DataCollectorOutput

    def __init__(
        self,
        *,
        price_provider: MarketDataProvider | None = None,
        facts_provider: MarketDataProvider | None = None,
        news_service: NewsFetcher | None = None,
        news_limit: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(provider="local", model="deterministic", **kwargs)
        self.price_provider = price_provider or get_default_market_data_provider()
        self.facts_provider = facts_provider or SECProvider()
        self.news_service = news_service or get_news_service()
        self.news_limit = news_limit

    async def execute(self, context: AnalysisContext) -> AgentExecutionPayload:
        symbol = normalize_symbol_value(context.request.symbol)
        warnings: list[str] = []
        missing_data: list[str] = []
        sources: list[DataSource] = []
        provider_names: list[str] = []

        price_result = await self._fetch_price_history(symbol, warnings)
        facts_result = await self._fetch_company_facts(symbol, warnings)
        news_result = await self._fetch_news(
            symbol,
            query=context.request.custom_question,
            language=context.request.language,
            warnings=warnings,
        )

        price_bars = price_result.bars if price_result else []
        company_profile = facts_result.profile if facts_result else None
        financials = facts_result.financials if facts_result else None
        news_items = news_result.to_news_items() if news_result else []

        if price_result:
            sources.append(price_result.source)
            warnings.extend(price_result.warnings)
            provider_names.append(price_result.provider)
        if facts_result:
            sources.append(facts_result.source)
            warnings.extend(facts_result.warnings)
            provider_names.append(facts_result.provider)
        if news_result:
            sources.append(news_result.source)
            warnings.extend(news_result.warnings)
            provider_names.append(news_result.provider)

        price_status = self._price_status(price_bars)
        news_status = self._news_status(news_result, news_items)
        fundamentals_status = self._fundamentals_status(company_profile, financials)

        if price_status == "missing":
            missing_data.append("price_history")
        if company_profile is None:
            missing_data.append("company_profile")
        if financials is None:
            missing_data.append("financials")
        if news_status == "missing":
            missing_data.append("news")

        indicators = None
        if price_bars:
            indicators = calculate_indicators(
                symbol,
                price_bars,
                horizon=context.request.horizon,
            )
            warnings.extend(indicators.warnings)
        else:
            warnings.append(
                "Technical indicators skipped because price history is missing."
            )

        deduped_warnings = self._dedupe(warnings)
        deduped_missing_data = self._dedupe(missing_data)
        data_quality = DataQualitySummary(
            price_data_status=price_status,
            news_data_status=news_status,
            fundamentals_status=fundamentals_status,
            provider_names=self._dedupe(provider_names),
            missing_data=deduped_missing_data,
            warnings=deduped_warnings,
            score=self._quality_score(
                price_bars=price_bars,
                company_profile_available=company_profile is not None,
                financials_available=financials is not None,
                news_items=news_items,
            ),
        )

        market_data = MarketDataBundle(
            symbol=symbol,
            market=context.request.market,
            price_history=price_bars,
            company_profile=company_profile,
            financials=financials,
            news=news_items,
            sources=sources,
            missing_data=deduped_missing_data,
            warnings=deduped_warnings,
            data_quality_score=data_quality.score,
        )

        context.market_data = market_data
        context.indicators = indicators
        context.data_quality = data_quality
        context.warnings = self._dedupe([*context.warnings, *deduped_warnings])

        return AgentExecutionPayload(
            status="completed" if price_bars else "partial",
            provider="local",
            model="deterministic",
            output=DataCollectorOutput(
                market_data=market_data,
                data_quality=data_quality,
            ),
            data_used=self._data_used(
                price_bars,
                company_profile,
                financials,
                news_items,
            ),
            warnings=deduped_warnings,
        )

    async def _fetch_price_history(
        self,
        symbol: str,
        warnings: list[str],
    ) -> PriceHistoryResult | None:
        try:
            return await self.price_provider.get_price_history(symbol)
        except Exception as exc:  # noqa: BLE001 - preserve partial analysis context.
            warnings.append(
                f"{self._provider_name(self.price_provider)} "
                f"price history failed: {exc}"
            )
            return None

    async def _fetch_company_facts(
        self,
        symbol: str,
        warnings: list[str],
    ) -> CompanyFactsResult | None:
        if not any(
            self.facts_provider.supports(capability)
            for capability in ("company_profile", "financials", "company_facts")
        ):
            warnings.append(
                f"{self._provider_name(self.facts_provider)} "
                "does not support company facts."
            )
            return None

        try:
            return await self.facts_provider.get_company_facts(symbol)
        except Exception as exc:  # noqa: BLE001 - profile/fundamentals are optional.
            warnings.append(
                f"{self._provider_name(self.facts_provider)} "
                f"company facts failed: {exc}"
            )
            return None

    async def _fetch_news(
        self,
        symbol: str,
        *,
        query: str | None,
        language: str,
        warnings: list[str],
    ) -> NewsProviderResult | None:
        try:
            return await self.news_service.get_news(
                symbol,
                query=query,
                limit=self.news_limit,
                language=language,
            )
        except Exception as exc:  # noqa: BLE001 - news is optional.
            warnings.append(f"news_service failed: {exc}")
            return None

    def _price_status(self, bars: Sequence[PriceBar]) -> DataStatus:
        return "available" if bars else "missing"

    def _news_status(
        self,
        result: NewsProviderResult | None,
        items: Sequence[NewsItem],
    ) -> DataStatus:
        if result is None:
            return "missing"
        if result.status in {"available", "partial"} and items:
            return result.status
        return "missing"

    def _fundamentals_status(
        self,
        company_profile_available: object | None,
        financials_available: object | None,
    ) -> DataStatus:
        if company_profile_available is not None and financials_available is not None:
            return "available"
        if company_profile_available is not None or financials_available is not None:
            return "partial"
        return "missing"

    def _quality_score(
        self,
        *,
        price_bars: Sequence[PriceBar],
        company_profile_available: bool,
        financials_available: bool,
        news_items: Sequence[NewsItem],
    ) -> float:
        score = 0.0
        if price_bars:
            score += 0.50
        if company_profile_available:
            score += 0.15
        if financials_available:
            score += 0.20
        if news_items:
            score += 0.15
        return round(min(score, 1.0), 2)

    def _data_used(
        self,
        price_bars: Sequence[PriceBar],
        company_profile: object | None,
        financials: object | None,
        news_items: Sequence[NewsItem],
    ) -> list[str]:
        data_used: list[str] = []
        if price_bars:
            data_used.append("price_history")
            data_used.append("technical_indicators")
        if company_profile is not None:
            data_used.append("company_profile")
        if financials is not None:
            data_used.append("financials")
        if news_items:
            data_used.append("news")
        return data_used

    def _provider_name(self, provider: object) -> str:
        return str(getattr(provider, "provider_name", provider.__class__.__name__))

    def _dedupe(self, values: Sequence[str]) -> list[str]:
        deduped: dict[str, None] = {}
        for value in values:
            stripped = value.strip()
            if stripped:
                deduped.setdefault(stripped, None)
        return list(deduped)


__all__ = ["DataCollectorAgent", "NewsFetcher"]
