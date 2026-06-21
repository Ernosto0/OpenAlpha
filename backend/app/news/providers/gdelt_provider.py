from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from backend.app.news.base import (
    NewsArticle,
    NewsProvider,
    NewsProviderError,
    NewsProviderResult,
    normalize_symbol,
    relevance_tokens,
)
from backend.app.orchestrator.schemas import DataSource


class GDELTProvider(NewsProvider):
    provider_name = "gdelt"
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"

    async def get_news(
        self,
        symbol: str,
        *,
        query: str | None = None,
        limit: int = 20,
        language: str = "en",
    ) -> NewsProviderResult:
        normalized_symbol = normalize_symbol(symbol)
        url = self._url(
            normalized_symbol,
            query=query,
            limit=limit,
            language=language,
        )
        text = await self._fetch_text(url)
        items = self._parse_response(
            text,
            symbol=normalized_symbol,
            query=query,
        )
        status = "available" if items else "missing"
        warnings: list[str] = []
        if not items:
            warnings.append(f"No GDELT headlines returned for {normalized_symbol}.")

        return NewsProviderResult(
            provider=self.provider_name,
            status=status,
            source=DataSource(
                name="GDELT global news",
                provider=self.provider_name,
                status=status,
                url=url,
                notes=["No API key required. Broad news search, not finance-specific."],
            ),
            items=items[: max(limit, 0)],
            warnings=warnings,
        )

    def _url(
        self,
        symbol: str,
        *,
        query: str | None,
        limit: int,
        language: str,
    ) -> str:
        params = {
            "query": self._query(symbol, query=query, language=language),
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(min(max(limit * 3, 10), 250)),
            "sort": "HybridRel",
        }
        return f"{self.base_url}?{urlencode(params)}"

    def _query(self, symbol: str, *, query: str | None, language: str) -> str:
        finance_terms = "(stock OR shares OR earnings OR revenue OR investor)"
        terms = f'"{symbol}" {finance_terms}'
        if query:
            terms = f'{terms} "{query.strip()}"'
        source_language = gdelt_source_language(language)
        if source_language:
            terms = f"{terms} sourcelang:{source_language}"
        return terms

    def _parse_response(
        self,
        text: str,
        *,
        symbol: str,
        query: str | None,
    ) -> list[NewsArticle]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise NewsProviderError(
                "Could not parse GDELT response",
                retryable=True,
            ) from exc

        articles = payload.get("articles", [])
        if not isinstance(articles, list):
            raise NewsProviderError("Unexpected GDELT article payload", retryable=True)

        items: list[NewsArticle] = []
        for article in articles:
            if not isinstance(article, dict):
                continue
            title = str(article.get("title") or "").strip()
            url = str(article.get("url") or "").strip() or None
            if not title:
                continue

            summary = str(article.get("snippet") or "").strip() or None
            source = (
                str(article.get("sourceCommonName") or "").strip()
                or str(article.get("domain") or "").strip()
                or "GDELT"
            )
            items.append(
                NewsArticle(
                    title=title,
                    source=source,
                    provider=self.provider_name,
                    published_at=parse_gdelt_datetime(article.get("seendate")),
                    url=url,
                    summary=summary,
                    relevance_score=self._initial_relevance(
                        title,
                        summary or "",
                        symbol=symbol,
                        query=query,
                    ),
                    symbols=[symbol],
                    raw={
                        "domain": article.get("domain"),
                        "language": article.get("language"),
                        "source_country": article.get("sourceCountry"),
                    },
                )
            )
        return items

    def _initial_relevance(
        self,
        title: str,
        summary: str,
        *,
        symbol: str,
        query: str | None,
    ) -> float:
        text = f"{title} {summary}".lower()
        tokens = relevance_tokens(symbol, query)
        if not tokens:
            return 0.1
        matches = sum(1 for token in tokens if token in text)
        return min(0.1 + (matches / len(tokens)) * 0.5, 1)


def parse_gdelt_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def gdelt_source_language(language: str) -> str | None:
    normalized = language.strip().lower()
    if not normalized:
        return None
    language_map = {
        "en": "english",
        "en-us": "english",
        "en-gb": "english",
        "tr": "turkish",
        "tr-tr": "turkish",
    }
    return language_map.get(normalized, normalized)
