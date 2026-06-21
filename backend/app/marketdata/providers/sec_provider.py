from __future__ import annotations

import json
from datetime import date
from typing import Any

from backend.app.marketdata.base import (
    CompanyFactsResult,
    MarketDataProvider,
    MarketDataProviderError,
    PriceHistoryResult,
    PriceInterval,
    normalize_symbol,
)
from backend.app.orchestrator.schemas import (
    CompanyProfile,
    DataSource,
    FinancialSnapshot,
)


class SECProvider(MarketDataProvider):
    provider_name = "sec_edgar"
    capabilities = ("company_profile", "financials", "filings", "company_facts")
    tickers_url = "https://www.sec.gov/files/company_tickers.json"
    facts_url = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    submissions_url = "https://data.sec.gov/submissions/CIK{cik}.json"

    def __init__(
        self,
        *,
        user_agent: str = "OpenAlpha local research app contact@example.com",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.user_agent = user_agent

    async def get_price_history(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        interval: PriceInterval = "1d",
    ) -> PriceHistoryResult:
        normalized = normalize_symbol(symbol)
        source = DataSource(
            name="Historical OHLCV",
            provider=self.provider_name,
            status="missing",
            notes=["SEC EDGAR does not provide market price history."],
        )
        return PriceHistoryResult(
            symbol=normalized,
            provider=self.provider_name,
            status="missing",
            source=source,
            warnings=["SEC EDGAR does not provide market price history."],
        )

    async def get_company_facts(self, symbol: str) -> CompanyFactsResult:
        normalized = normalize_symbol(symbol)
        headers = {"User-Agent": self.user_agent, "Accept-Encoding": "identity"}
        ticker_payload = json.loads(
            await self._fetch_text(self.tickers_url, headers=headers)
        )
        cik, title = self._resolve_cik(normalized, ticker_payload)
        padded_cik = str(cik).zfill(10)

        facts_url = self.facts_url.format(cik=padded_cik)
        submissions_url = self.submissions_url.format(cik=padded_cik)
        facts = json.loads(await self._fetch_text(facts_url, headers=headers))
        submissions = json.loads(
            await self._fetch_text(submissions_url, headers=headers)
        )

        return CompanyFactsResult(
            symbol=normalized,
            provider=self.provider_name,
            status="available",
            source=DataSource(
                name="SEC EDGAR company facts and filings",
                provider=self.provider_name,
                status="available",
                url=facts_url,
                notes=["Official SEC EDGAR data. Requires a compliant User-Agent."],
            ),
            profile=CompanyProfile(
                name=facts.get("entityName") or title,
                country="US",
            ),
            financials=self._financial_snapshot(facts),
            filings=self._recent_filings(submissions),
            company_facts=facts,
        )

    def _resolve_cik(
        self,
        symbol: str,
        payload: dict[str, Any],
    ) -> tuple[int, str | None]:
        for item in payload.values():
            if str(item.get("ticker", "")).upper() == symbol:
                return int(item["cik_str"]), item.get("title")
        raise MarketDataProviderError(f"SEC CIK not found for symbol {symbol}")

    def _financial_snapshot(self, facts: dict[str, Any]) -> FinancialSnapshot:
        concepts = facts.get("facts", {}).get("us-gaap", {})
        revenue = self._latest_concept_value(
            concepts,
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
        )
        net_income = self._latest_concept_value(concepts, "NetIncomeLoss")
        eps = self._latest_concept_value(
            concepts,
            "EarningsPerShareDiluted",
            "EarningsPerShareBasic",
        )
        operating_income = self._latest_concept_value(concepts, "OperatingIncomeLoss")
        gross_profit = self._latest_concept_value(concepts, "GrossProfit")
        equity = self._latest_concept_value(concepts, "StockholdersEquity")
        liabilities = self._latest_concept_value(concepts, "Liabilities")

        return FinancialSnapshot(
            revenue=revenue,
            gross_margin=self._ratio(gross_profit, revenue),
            operating_margin=self._ratio(operating_income, revenue),
            net_income=net_income,
            eps=eps,
            debt_to_equity=self._ratio(liabilities, equity),
            metadata={
                "source": "SEC companyfacts",
                "cik": facts.get("cik"),
                "entity_name": facts.get("entityName"),
            },
        )

    def _latest_concept_value(
        self,
        concepts: dict[str, Any],
        *names: str,
    ) -> float | None:
        for name in names:
            units = concepts.get(name, {}).get("units", {})
            for unit_values in units.values():
                values = [
                    value
                    for value in unit_values
                    if value.get("val") is not None
                    and value.get("form") in {"10-K", "10-Q"}
                ]
                if not values:
                    continue
                values.sort(key=lambda value: value.get("end", ""), reverse=True)
                return float(values[0]["val"])
        return None

    def _ratio(
        self,
        numerator: float | None,
        denominator: float | None,
    ) -> float | None:
        if numerator is None or denominator in {None, 0}:
            return None
        return numerator / denominator

    def _recent_filings(self, submissions: dict[str, Any]) -> list[dict[str, Any]]:
        recent = submissions.get("filings", {}).get("recent", {})
        accession_numbers = recent.get("accessionNumber", [])
        forms = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        primary_documents = recent.get("primaryDocument", [])
        filings: list[dict[str, Any]] = []

        for index, accession_number in enumerate(accession_numbers[:20]):
            filings.append(
                {
                    "accession_number": accession_number,
                    "form": self._list_value(forms, index),
                    "filing_date": self._list_value(filing_dates, index),
                    "primary_document": self._list_value(primary_documents, index),
                }
            )
        return filings

    def _list_value(self, values: list[Any], index: int) -> Any:
        return values[index] if index < len(values) else None
