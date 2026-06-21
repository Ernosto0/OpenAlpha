from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.orchestrator.schemas import (
    DataSource,
    NewsItem,
    normalize_symbol_value,
)


NewsDataStatus = Literal["available", "partial", "missing"]
TextTransport = Callable[[str, Mapping[str, str] | None, float], str]
AsyncTextTransport = Callable[[str, Mapping[str, str] | None, float], Awaitable[str]]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NewsProviderError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class NewsProviderConfigurationError(NewsProviderError):
    pass


class NewsArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    provider: str = Field(min_length=1, max_length=64)
    published_at: datetime | None = None
    url: str | None = None
    summary: str | None = None
    sentiment_score: float | None = Field(default=None, ge=-1, le=1)
    relevance_score: float = Field(default=0, ge=0, le=1)
    symbols: list[str] = Field(default_factory=list)
    event_type: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbols", mode="before")
    @classmethod
    def normalize_symbols(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        return [normalize_symbol_value(item) for item in value]

    def to_news_item(self) -> NewsItem:
        return NewsItem(
            title=self.title,
            source=self.source,
            published_at=self.published_at,
            url=self.url,
            summary=self.summary,
            sentiment_score=self.sentiment_score,
        )


class NewsProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=64)
    status: NewsDataStatus = "available"
    source: DataSource
    items: list[NewsArticle] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=utc_now)

    def to_news_items(self) -> list[NewsItem]:
        return [item.to_news_item() for item in self.items]


class NewsProvider(ABC):
    provider_name: str

    def __init__(
        self,
        *,
        timeout_seconds: float = 20,
        transport: TextTransport | AsyncTextTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    @abstractmethod
    async def get_news(
        self,
        symbol: str,
        *,
        query: str | None = None,
        limit: int = 20,
        language: str = "en",
    ) -> NewsProviderResult:
        raise NotImplementedError

    async def _fetch_text(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        if self.transport is None:
            return await asyncio.to_thread(
                default_text_transport,
                url,
                headers,
                self.timeout_seconds,
            )

        result = self.transport(url, headers, self.timeout_seconds)
        if asyncio.iscoroutine(result):
            return await result
        return result


class PlaceholderNewsProvider(NewsProvider):
    provider_name = "placeholder"

    async def get_news(
        self,
        symbol: str,
        *,
        query: str | None = None,
        limit: int = 20,
        language: str = "en",
    ) -> NewsProviderResult:
        normalize_symbol(symbol)
        warning = f"{self.provider_name} is a placeholder and is not implemented in v1."
        return NewsProviderResult(
            provider=self.provider_name,
            status="missing",
            source=DataSource(
                name="News",
                provider=self.provider_name,
                status="missing",
                notes=[warning],
            ),
            warnings=[warning],
            items=[],
        )


class NewsService:
    def __init__(self, providers: Sequence[NewsProvider] | None = None) -> None:
        self.providers = (
            list(providers) if providers is not None else get_default_news_providers()
        )

    async def get_news(
        self,
        symbol: str,
        *,
        query: str | None = None,
        limit: int = 20,
        language: str = "en",
    ) -> NewsProviderResult:
        normalized_symbol = normalize_symbol(symbol)
        warnings: list[str] = []
        sources: list[DataSource] = []
        items: list[NewsArticle] = []

        for provider in self.providers:
            try:
                result = await provider.get_news(
                    normalized_symbol,
                    query=query,
                    limit=limit,
                    language=language,
                )
            except Exception as exc:  # noqa: BLE001 - preserve partial news data.
                warnings.append(f"{provider.provider_name} failed: {exc}")
                sources.append(
                    DataSource(
                        name="News",
                        provider=provider.provider_name,
                        status="missing",
                        notes=[str(exc)],
                    )
                )
                continue

            sources.append(result.source)
            warnings.extend(result.warnings)
            items.extend(result.items)

        scored = self._dedupe_items(
            self._score_item(item, normalized_symbol, query=query)
            for item in items
        )
        scored.sort(
            key=lambda item: (
                item.relevance_score,
                item.published_at or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )

        limited_items = scored[: max(limit, 0)]
        status: NewsDataStatus
        if limited_items and warnings:
            status = "partial"
        elif limited_items:
            status = "available"
        else:
            status = "missing"

        source_notes = self._source_notes(sources)
        return NewsProviderResult(
            provider="news_service",
            status=status,
            source=DataSource(
                name="Aggregated news",
                provider="news_service",
                status=status,
                notes=source_notes,
            ),
            items=limited_items,
            warnings=dedupe_text(warnings),
        )

    def _dedupe_items(self, items: Iterable[NewsArticle]) -> list[NewsArticle]:
        deduped: dict[str, NewsArticle] = {}
        for item in items:
            key = canonical_item_key(item)
            existing = deduped.get(key)
            if existing is None or item.relevance_score > existing.relevance_score:
                deduped[key] = item
        return list(deduped.values())

    def _score_item(
        self,
        item: NewsArticle,
        symbol: str,
        *,
        query: str | None,
    ) -> NewsArticle:
        tokens = relevance_tokens(symbol, query)
        text = " ".join(
            part
            for part in [item.title, item.summary or "", item.source, item.url or ""]
            if part
        ).lower()
        score = item.relevance_score

        if symbol.lower() in text or symbol in item.symbols:
            score += 0.5
        if (
            item.provider in {"yahoo_finance_rss", "sec_edgar_news"}
            and symbol in item.symbols
        ):
            score += 0.2
        if tokens:
            matches = sum(1 for token in tokens if token in text)
            score += min(matches / len(tokens), 1) * 0.35
        if item.published_at:
            score += 0.1

        return item.model_copy(update={"relevance_score": min(score, 1)})

    def _source_notes(self, sources: Sequence[DataSource]) -> list[str]:
        notes: list[str] = []
        for source in sources:
            notes.append(f"{source.provider}: {source.status}")
        return notes


def default_text_transport(
    url: str,
    headers: Mapping[str, str] | None,
    timeout_seconds: float,
) -> str:
    from urllib.request import Request, urlopen

    request = Request(url, headers=dict(headers or {}))
    with urlopen(request, timeout=timeout_seconds) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def normalize_symbol(symbol: str) -> str:
    return normalize_symbol_value(symbol)


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def canonical_item_key(item: NewsArticle) -> str:
    if item.url:
        return canonical_url(item.url)
    published = item.published_at.date().isoformat() if item.published_at else ""
    normalized_title = re.sub(r"\s+", " ", item.title.strip().lower())
    return f"{normalized_title}|{item.source.lower()}|{published}"


def relevance_tokens(symbol: str, query: str | None = None) -> list[str]:
    raw = [symbol, *(query or "").split()]
    tokens = []
    for token in raw:
        cleaned = re.sub(r"[^A-Za-z0-9._-]", "", token).lower()
        if len(cleaned) >= 2:
            tokens.append(cleaned)
    return list(dict.fromkeys(tokens))


def dedupe_text(values: Iterable[str]) -> list[str]:
    deduped: dict[str, None] = {}
    for value in values:
        stripped = value.strip()
        if stripped:
            deduped.setdefault(stripped, None)
    return list(deduped)


def get_default_news_providers() -> list[NewsProvider]:
    from backend.app.news.providers.gdelt_provider import GDELTProvider
    from backend.app.news.providers.rss_provider import RSSProvider
    from backend.app.news.providers.sec_edgar_provider import SecEdgarNewsProvider
    from backend.app.news.providers.yahoo_finance_rss_provider import (
        YahooFinanceRssProvider,
    )

    return [
        GDELTProvider(),
        RSSProvider(),
        YahooFinanceRssProvider(),
        SecEdgarNewsProvider(),
    ]


def get_news_service(providers: Sequence[NewsProvider] | None = None) -> NewsService:
    return NewsService(providers=providers)


async def get_news(
    symbol: str,
    *,
    query: str | None = None,
    limit: int = 20,
    language: str = "en",
    providers: Sequence[NewsProvider] | None = None,
) -> NewsProviderResult:
    return await NewsService(providers=providers).get_news(
        symbol,
        query=query,
        limit=limit,
        language=language,
    )


__all__ = [
    "AsyncTextTransport",
    "NewsArticle",
    "NewsDataStatus",
    "NewsProvider",
    "NewsProviderConfigurationError",
    "NewsProviderError",
    "NewsProviderResult",
    "NewsService",
    "PlaceholderNewsProvider",
    "TextTransport",
    "dedupe_text",
    "get_default_news_providers",
    "get_news",
    "get_news_service",
    "normalize_symbol",
    "relevance_tokens",
]
