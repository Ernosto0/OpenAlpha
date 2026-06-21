from __future__ import annotations

from backend.app.news.base import PlaceholderNewsProvider


class AlphaVantageNewsProvider(PlaceholderNewsProvider):
    provider_name = "alpha_vantage"
