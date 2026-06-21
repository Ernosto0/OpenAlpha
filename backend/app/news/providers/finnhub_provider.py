from __future__ import annotations

from backend.app.news.base import PlaceholderNewsProvider


class FinnhubNewsProvider(PlaceholderNewsProvider):
    provider_name = "finnhub"
