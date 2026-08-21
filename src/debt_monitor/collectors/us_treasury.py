"""US Treasury: FiscalData debt-to-the-penny (daily) + daily par yield curve.

The FiscalData service prefix must be `fiscal_service/v2` (dossier 02); the
par-yield CSVs are served per calendar year with rows newest-first.
"""

import asyncio
import io
import re
from datetime import UTC, datetime

import polars as pl

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult, Observation

# FiscalData metadata fields (record_*, src_line_nbr) must not become series.
_AMOUNT_FIELD = re.compile(r"(debt|hold|amt)", re.I)

DEBT_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/"
    "accounting/od/debt_to_penny"
)
YIELD_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
)
YIELD_PARAMS = {
    "type": "daily_treasury_yield_curve",
    "field_tdr_date_value": "",
    "page": "",
    "_format": "csv",
}


def parse_debt_records(records: list[dict]) -> list[Observation]:
    """Store the debt amount fields; amounts arrive as strings."""
    out: list[Observation] = []
    for rec in records:
        period = str(rec.get("record_date", ""))
        if not period:
            continue
        for key, raw in rec.items():
            if not _AMOUNT_FIELD.match(key) or raw is None:
                continue
            try:
                value = float(raw)
            except TypeError, ValueError:
                continue
            out.append(
                Observation(
                    source="us_treasury",
                    dataset="debt_to_penny",
                    series=key,
                    country="US",
                    period=period,
                    period_type="day",
                    value=value,
                    unit="USD",
                )
            )
    return out


def parse_yield_csv(text: str) -> list[Observation]:
    df = pl.read_csv(io.BytesIO(text.encode()))
    maturity_cols = [c for c in df.columns if c.lower() != "date"]
    out: list[Observation] = []
    for row in df.iter_rows(named=True):
        raw_date = str(row.get("Date", "") or row.get("date", ""))
        try:
            period = datetime.strptime(raw_date, "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
            continue
        for col in maturity_cols:
            raw = row.get(col)
            try:
                value = float(raw)
            except TypeError, ValueError:
                continue
            out.append(
                Observation(
                    source="us_treasury",
                    dataset="par_yield_curve",
                    series=col,
                    country="US",
                    period=period,
                    period_type="day",
                    value=value,
                    unit="percent",
                )
            )
    return out


@register
class UsTreasuryCollector(BaseCollector):
    name = "us_treasury"
    collection = "us_treasury"
    description = "US Treasury debt-to-the-penny daily + daily par yield curve"

    async def collect(self) -> CollectResult:
        parts: list[str] = []
        total = 0

        payload = await self.http.get_json(
            DEBT_URL, params={"sort": "-record_date", "page[size]": "120"}
        )
        debt_obs = parse_debt_records(payload.get("data", []))
        total += await self.upsert(debt_obs)
        parts.append(f"debt_to_penny: {len(debt_obs)}")

        current_year = datetime.now(UTC).year
        for year in (current_year, current_year - 1):
            params = dict(YIELD_PARAMS)
            params["field_tdr_date_value"] = str(year)
            text = await self.http.get_text(YIELD_URL.format(year=year), params=params)
            curve_obs = parse_yield_csv(text)
            total += await self.upsert(curve_obs)
            parts.append(f"yields {year}: {len(curve_obs)}")
            await asyncio.sleep(0.3)

        return CollectResult(source=self.name, status="ok", n_docs=total, detail="; ".join(parts))
