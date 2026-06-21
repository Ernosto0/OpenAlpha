from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any

from backend.app.news.base import (
    NewsArticle,
    NewsProvider,
    NewsProviderError,
    NewsProviderResult,
    normalize_symbol,
    relevance_tokens,
)
from backend.app.orchestrator.schemas import DataSource


class RSSProvider(NewsProvider):
    provider_name = "rss"
    default_feed_urls = (
        "https://feeds.finance.yahoo.com/rss/2.0/topstories?region=US&lang=en-US",
        "https://www.marketwatch.com/rss/topstories",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    )

    def __init__(self, *, feed_urls: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.feed_urls = feed_urls or list(self.default_feed_urls)

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
        items: list[NewsArticle] = []

        for feed_url in self.feed_urls:
            try:
                text = await self._fetch_text(feed_url)
                feed_items = self._parse_feed(
                    text,
                    feed_url=feed_url,
                    symbol=normalized_symbol,
                    query=query,
                )
            except Exception as exc:  # noqa: BLE001 - RSS fallback should be partial.
                warnings.append(f"RSS feed failed ({feed_url}): {exc}")
                continue
            items.extend(feed_items)

        filtered = self._filter_relevant(items, normalized_symbol, query=query)
        status = "available" if filtered else "missing"
        if not filtered:
            warnings.append(f"No curated RSS headlines matched {normalized_symbol}.")

        return NewsProviderResult(
            provider=self.provider_name,
            status=status,
            source=DataSource(
                name="Curated RSS feeds",
                provider=self.provider_name,
                status=status,
                notes=["Generic curated-feed fallback; relevance is best effort."],
            ),
            items=filtered[: max(limit, 0)],
            warnings=warnings,
        )

    def _parse_feed(
        self,
        text: str,
        *,
        feed_url: str,
        symbol: str,
        query: str | None,
    ) -> list[NewsArticle]:
        try:
            root = ET.fromstring(text.strip())
        except ET.ParseError as exc:
            raise NewsProviderError("Could not parse RSS feed") from exc

        entries = [
            element
            for element in root.iter()
            if local_name(element.tag) in {"item", "entry"}
        ]
        items: list[NewsArticle] = []
        for entry in entries:
            title = clean_text(child_text(entry, "title"))
            if not title:
                continue

            link = self._entry_link(entry)
            source = clean_text(child_text(entry, "source")) or feed_source(feed_url)
            summary = clean_text(
                child_text(entry, "description")
                or child_text(entry, "summary")
                or child_text(entry, "content")
            )
            published_at = parse_datetime(
                child_text(entry, "pubDate")
                or child_text(entry, "published")
                or child_text(entry, "updated")
                or child_text(entry, "dc:date")
            )

            items.append(
                NewsArticle(
                    title=title,
                    source=source,
                    provider=self.provider_name,
                    published_at=published_at,
                    url=link,
                    summary=summary or None,
                    relevance_score=self._initial_relevance(
                        title,
                        summary,
                        symbol=symbol,
                        query=query,
                    ),
                    symbols=[symbol],
                    raw={"feed_url": feed_url},
                )
            )
        return items

    def _entry_link(self, entry: ET.Element) -> str | None:
        link = child_text(entry, "link")
        if link:
            return link.strip()
        for child in entry:
            if local_name(child.tag) == "link":
                href = child.attrib.get("href")
                if href:
                    return href.strip()
        return None

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
            return 0
        matches = sum(1 for token in tokens if token in text)
        return min(matches / len(tokens), 1) * 0.5

    def _filter_relevant(
        self,
        items: list[NewsArticle],
        symbol: str,
        *,
        query: str | None,
    ) -> list[NewsArticle]:
        tokens = relevance_tokens(symbol, query)
        if not tokens:
            return items

        filtered: list[NewsArticle] = []
        for item in items:
            text = f"{item.title} {item.summary or ''} {item.url or ''}".lower()
            if any(token in text for token in tokens):
                filtered.append(item)
        return filtered


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(element: ET.Element, name: str) -> str:
    wanted = name.split(":", 1)[-1]
    for child in element:
        if local_name(child.tag) == wanted and child.text:
            return child.text
    return ""


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", unescape(value))
    return re.sub(r"\s+", " ", without_tags).strip()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    stripped = value.strip()
    try:
        parsed = parsedate_to_datetime(stripped)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError, OverflowError):
        pass

    try:
        parsed = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def feed_source(feed_url: str) -> str:
    match = re.search(r"https?://(?:www\.)?([^/]+)", feed_url)
    return match.group(1) if match else "RSS"
