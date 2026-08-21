"""FRED official API (api.stlouisfed.org) — US detail + market spreads.

The account guide's keyless fredgraph-over-HTTP workaround is retired in favour
of FRED_API_KEY. FRED is used for US series and market spreads only — its
international OECD/BIS mirrors are stale or gone (dossier 01/05/06).
"""

import asyncio

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult, Observation, PeriodType

OBS_URL = "https://api.stlouisfed.org/fred/series/observations"
PAGE = 10_000

# (series_id, period_type, country, label)
SERIES: tuple[tuple[str, PeriodType, str, str], ...] = (
    ("GDP", "quarter", "US", "Real GDP, quarterly"),
    ("CPIAUCSL", "month", "US", "CPI all urban consumers, index"),
    ("GFDEGDQ188S", "quarter", "US", "Federal debt %GDP"),
    ("DGS3MO", "day", "US", "3-month Treasury bill"),
    ("DGS2", "day", "US", "2-year Treasury note"),
    ("DGS10", "day", "US", "10-year Treasury note"),
    ("DGS30", "day", "US", "30-year Treasury bond"),
    ("T10Y3M", "day", "US", "10Y-3M Treasury spread"),
    ("BAMLC0A0CM", "day", "US", "ICE BofA US corporate IG OAS"),
    ("BAMLH0A0HYM2", "day", "US", "ICE BofA US high yield OAS"),
    ("BAMLEMCBPIOAS", "day", "US", "ICE BofA EUR corporate IG OAS"),
    ("BAMLHE00EHYIOAS", "day", "US", "ICE BofA EUR high yield OAS"),
    ("DRCCLACBS", "quarter", "US", "Credit-card 90+ day delinquency"),
    ("DRSFRMACBS", "quarter", "US", "Mortgage 90+ day delinquency"),
    ("DRCLACBS", "quarter", "US", "Consumer loan delinquency"),
    ("DRTSCILM", "quarter", "US", "C&I loan delinquency"),
    ("DRBLACBS", "quarter", "US", "Business loan delinquency"),
    ("DRCRELEXFACBS", "quarter", "US", "CRE excluded-farm delinquency"),
    ("CORCCACBS", "quarter", "US", "Credit-card charge-off rate"),
    ("MORTGAGE30US", "week", "US", "30-year fixed mortgage rate"),
    ("IR3TIB01USM156N", "month", "US", "3-month interbank rate"),
    ("IRLTLT01DEM156N", "month", "DE", "Germany 10Y gov bond"),
    ("IRLTLT01JPM156N", "month", "JP", "Japan 10Y gov bond"),
    ("IRLTLT01GBM156N", "month", "GB", "UK 10Y gov bond"),
    ("IRLTLT01USM156N", "month", "US", "US 10Y gov bond (LT av)"),
)


def canonical_period(date: str, period_type: str) -> str:
    year, month = int(date[:4]), int(date[5:7])
    if period_type == "month":
        return f"{year:04d}-{month:02d}"
    if period_type == "quarter":
        return f"{year:04d}-Q{(month - 1) // 3 + 1}"
    return date


@register
class FredCollector(BaseCollector):
    name = "fred"
    collection = "fred"
    description = "FRED API: US CPI/GDP/debt, yields, BofA spreads, delinquency, mortgage"

    async def collect(self) -> CollectResult:
        if not self.settings.fred_api_key:
            return CollectResult(source=self.name, status="skipped", detail="FRED_API_KEY not set")
        parts: list[str] = []
        total = 0
        for series_id, period_type, country, label in SERIES:
            observations = await self._fetch_series(series_id, period_type, country, label)
            if observations:
                total += await self.upsert(observations)
                parts.append(f"{series_id}: {len(observations)}")
            else:
                parts.append(f"{series_id}: EMPTY")
            await asyncio.sleep(0.3)
        return CollectResult(source=self.name, status="ok", n_docs=total, detail="; ".join(parts))

    async def _fetch_series(
        self, series_id: str, period_type: str, country: str, label: str
    ) -> list[Observation]:
        observations: list[Observation] = []
        offset = 0
        while True:
            payload = await self.http.get_json(
                OBS_URL,
                params={
                    "series_id": series_id,
                    "api_key": self.settings.fred_api_key,
                    "file_type": "json",
                    "sort_order": "asc",
                    "limit": PAGE,
                    "offset": offset,
                },
            )
            batch = payload.get("observations", [])
            for item in batch:
                raw = item.get("value", ".")
                if raw in (".", "", None):
                    continue
                observations.append(
                    self.obs(
                        dataset="FRED",
                        series=series_id,
                        country=country,
                        period=canonical_period(item["date"], period_type),
                        period_type=period_type,
                        value=float(raw),
                        unit="native",
                        dimensions={"label": label},
                    )
                )
            if len(batch) < PAGE:
                return observations
            offset += PAGE
