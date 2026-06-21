from __future__ import annotations

import json
from datetime import datetime, time, timezone
from typing import Any

from backend.app.news.base import (
    NewsArticle,
    NewsProvider,
    NewsProviderError,
    NewsProviderResult,
    normalize_symbol,
)
from backend.app.orchestrator.schemas import DataSource


class SecEdgarNewsProvider(NewsProvider):
    provider_name = "sec_edgar_news"
    tickers_url = "https://www.sec.gov/files/company_tickers.json"
    submissions_url = "https://data.sec.gov/submissions/CIK{cik}.json"

    def __init__(
        self,
        *,
        user_agent: str = "OpenAlpha local research app contact@example.com",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.user_agent = user_agent

    async def get_news(
        self,
        symbol: str,
        *,
        query: str | None = None,
        limit: int = 20,
        language: str = "en",
    ) -> NewsProviderResult:
        normalized_symbol = normalize_symbol(symbol)
        headers = {"User-Agent": self.user_agent, "Accept-Encoding": "identity"}
        ticker_payload = json.loads(
            await self._fetch_text(self.tickers_url, headers=headers)
        )
        cik, title = self._resolve_cik(normalized_symbol, ticker_payload)
        padded_cik = str(cik).zfill(10)
        submissions_url = self.submissions_url.format(cik=padded_cik)
        submissions = json.loads(
            await self._fetch_text(submissions_url, headers=headers)
        )
        items = self._recent_filings(
            submissions,
            cik=cik,
            symbol=normalized_symbol,
            company_name=title,
            limit=limit,
        )
        status = "available" if items else "missing"
        warnings = ["SEC EDGAR returns official filings/events, not editorial news."]
        if not items:
            warnings.append(f"No recent SEC filings returned for {normalized_symbol}.")

        return NewsProviderResult(
            provider=self.provider_name,
            status=status,
            source=DataSource(
                name="SEC EDGAR filings/events",
                provider=self.provider_name,
                status=status,
                url=submissions_url,
                notes=["Official SEC EDGAR data. Requires a compliant User-Agent."],
            ),
            items=items,
            warnings=warnings,
        )

    def _resolve_cik(
        self,
        symbol: str,
        payload: dict[str, Any],
    ) -> tuple[int, str | None]:
        for item in payload.values():
            if str(item.get("ticker", "")).upper() == symbol:
                return int(item["cik_str"]), item.get("title")
        raise NewsProviderError(f"SEC CIK not found for symbol {symbol}")

    def _recent_filings(
        self,
        submissions: dict[str, Any],
        *,
        cik: int,
        symbol: str,
        company_name: str | None,
        limit: int,
    ) -> list[NewsArticle]:
        recent = submissions.get("filings", {}).get("recent", {})
        accession_numbers = recent.get("accessionNumber", [])
        forms = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        primary_documents = recent.get("primaryDocument", [])
        descriptions = recent.get("primaryDocDescription", [])
        items: list[NewsArticle] = []

        for index, accession_number in enumerate(accession_numbers[: max(limit, 0)]):
            form = self._list_value(forms, index) or "filing"
            filing_date = self._list_value(filing_dates, index)
            report_date = self._list_value(report_dates, index)
            document = self._list_value(primary_documents, index)
            description = self._list_value(descriptions, index)
            title = self._title(
                symbol,
                form=form,
                description=description,
                company_name=company_name,
            )
            items.append(
                NewsArticle(
                    title=title,
                    source="SEC EDGAR",
                    provider=self.provider_name,
                    published_at=parse_sec_date(filing_date),
                    url=self._filing_url(cik, accession_number, document),
                    summary=self._summary(
                        form=form,
                        filing_date=filing_date,
                        report_date=report_date,
                        description=description,
                    ),
                    relevance_score=0.9,
                    symbols=[symbol],
                    event_type=form,
                    raw={
                        "accession_number": accession_number,
                        "form": form,
                        "filing_date": filing_date,
                        "report_date": report_date,
                        "primary_document": document,
                    },
                )
            )
        return items

    def _title(
        self,
        symbol: str,
        *,
        form: str,
        description: str | None,
        company_name: str | None,
    ) -> str:
        entity = company_name or symbol
        if description:
            return f"{entity} filed {form}: {description}"
        return f"{entity} filed {form}"

    def _summary(
        self,
        *,
        form: str,
        filing_date: str | None,
        report_date: str | None,
        description: str | None,
    ) -> str:
        parts = [f"Official SEC EDGAR {form} filing."]
        if description:
            parts.append(description)
        if filing_date:
            parts.append(f"Filing date: {filing_date}.")
        if report_date:
            parts.append(f"Report date: {report_date}.")
        return " ".join(parts)

    def _filing_url(
        self,
        cik: int,
        accession_number: str,
        primary_document: str | None,
    ) -> str | None:
        if not accession_number:
            return None
        accession_path = accession_number.replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_path}"
        if primary_document:
            return f"{base}/{primary_document}"
        return base

    def _list_value(self, values: list[Any], index: int) -> Any:
        return values[index] if index < len(values) else None


def parse_sec_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed_date = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)
