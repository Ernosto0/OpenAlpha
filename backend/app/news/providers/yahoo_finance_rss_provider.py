from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from backend.app.news.base import NewsProviderResult, normalize_symbol
from backend.app.news.providers.rss_provider import RSSProvider
from backend.app.orchestrator.schemas import DataSource


class YahooFinanceRssProvider(RSSProvider):
    provider_name = "yahoo_finance_rss"
    base_url = "https://feeds.finance.yahoo.com/rss/2.0/headline"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(feed_urls=[], **kwargs)

    async def get_news(
        self,
        symbol: str,
        *,
        query: str | None = None,
        limit: int = 20,
        language: str = "en",
    ) -> NewsProviderResult:
        normalized_symbol = normalize_symbol(symbol)
        url = self._feed_url(normalized_symbol, language=language)
        text = await self._fetch_text(url)
        items = self._parse_feed(
            text,
            feed_url=url,
            symbol=normalized_symbol,
            query=query,
        )
        status = "available" if items else "missing"
        warnings = ["Yahoo Finance RSS is an unofficial fallback."]
        if not items:
            warnings.append(
                f"No Yahoo Finance RSS headlines returned for {normalized_symbol}."
            )

        return NewsProviderResult(
            provider=self.provider_name,
            status=status,
            source=DataSource(
                name="Yahoo Finance RSS headlines",
                provider=self.provider_name,
                status=status,
                url=url,
                notes=["Unofficial finance-headline fallback; not guaranteed."],
            ),
            items=items[: max(limit, 0)],
            warnings=warnings,
        )

    def _feed_url(self, symbol: str, *, language: str) -> str:
        params = {
            "s": symbol,
            "region": "US",
            "lang": "en-US" if language.lower().startswith("en") else language,
        }
        return f"{self.base_url}?{urlencode(params)}"
