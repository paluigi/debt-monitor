"""BIS bulk statistics: Total Credit (WS_TC) + Debt Service Ratios (WS_DSR)
+ Debt Securities Statistics (WS_NA_SEC_DSS).

Bulk zips live only at data.bis.org/static/bulk/... (dossier 01); SDMX data
queries 404, so the wide-format CSVs are the supported path. Period columns are
melted into long observations; all non-period columns become dimensions.

WS_NA_SEC_DSS (dossier 11): 146k series rows — must be filtered to the issuer
maturity view before melting or the observation count explodes. Kept rows:
issuer sectors S13/S11/S12, quarterly, stocks (LE), liabilities, market value,
all currencies/markets, maturities S (original <=1y), LS (original >1y with
residual <=1y) and T (total). Securities maturing within a year = S + LS.
US has no LS split (original-maturity only) — documented in dossier 11.
"""

import asyncio
import io
import re

import polars as pl

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.http import unzip_members
from debt_monitor.models import CollectResult, Observation, classify_period

BULK_URL = "https://data.bis.org/static/bulk/{flow}_csv_col.zip"
FLOWS = ("WS_TC", "WS_DSR", "WS_NA_SEC_DSS")
PERIOD_COL = re.compile(r"^\d{4}(-Q[1-4]|-\d{2}(-\d{2})?)?$")

# Row filter for WS_NA_SEC_DSS (dimension code -> allowed values).
DSS_ROW_FILTER: dict[str, tuple[str, ...]] = {
    "REF_SECTOR": ("S13", "S11", "S12"),
    "FREQ": ("Q",),
    "STO": ("LE",),
    "ACCOUNTING_ENTRY": ("L",),
    "MATURITY": ("S", "LS", "T"),
    "VALUATION": ("M",),
    "CURRENCY_DENOM": ("_T",),
    "CUST_BREAKDOWN": ("_T",),
}
# DSS carries code+label column pairs; keep only the code columns as dimensions.
DSS_DIM_COLS = (
    "FREQ", "REF_AREA", "COUNTERPART_AREA", "COUNTERPART_SECTOR", "REF_SECTOR",
    "CONSOLIDATION", "ACCOUNTING_ENTRY", "STO", "INSTR_ASSET", "MATURITY",
    "UNIT_MEASURE", "CURRENCY_DENOM", "VALUATION", "UNIT_MULT",
)


class BisParser:
    """Parse one BIS csv_col zip member into observations."""

    def parse(self, flow: str, data: bytes) -> list[Observation]:
        members = unzip_members(data)
        csv_members = {n: b for n, b in members.items() if n.lower().endswith(".csv")}
        if not csv_members:
            raise ValueError(f"{flow}: zip contains no CSV members: {list(members)}")
        # Bulk zips may carry a metadata CSV; the data file is the largest.
        name = max(csv_members, key=lambda n: len(csv_members[n]))
        # DSS period columns mix ints and floats — read everything as strings.
        df = pl.read_csv(io.BytesIO(csv_members[name]), infer_schema_length=0)
        if flow == "WS_NA_SEC_DSS":
            df = df.filter(
                pl.all_horizontal(
                    [
                        pl.col(dim).is_in(list(values))
                        for dim, values in DSS_ROW_FILTER.items()
                        if dim in df.columns
                    ]
                )
            )
            keep = [c for c in DSS_DIM_COLS if c in df.columns] + [
                c for c in df.columns if PERIOD_COL.match(c.strip())
            ]
            df = df.select(keep)
            df = df.with_columns(pl.all().cast(pl.String, strict=False))
        period_cols = [c for c in df.columns if PERIOD_COL.match(c.strip())]
        dim_cols = [c for c in df.columns if c not in period_cols]
        if not period_cols:
            raise ValueError(f"{flow}: no period columns recognised in {df.columns}")
        country_col = next((c for c in dim_cols if "country" in c.lower()), "")
        if flow == "WS_NA_SEC_DSS":
            country_col = "REF_AREA"
        long = (
            df.unpivot(index=dim_cols, on=period_cols, variable_name="period", value_name="value")
            .drop_nulls("value")
            .with_columns(pl.col("value").cast(pl.Float64, strict=False))
            .drop_nulls("value")
        )
        unit_map = {"770": "% of GDP", "799": "ratio"}
        observations: list[Observation] = []
        for row in long.iter_rows(named=True):
            dims = {c: row[c] for c in dim_cols if row[c] is not None}
            unit_code = str(dims.get("UNIT_TYPE", ""))
            observations.append(
                Observation(
                    source="bis",
                    dataset=flow,
                    series=":".join(str(dims.get(c, "")) for c in dim_cols if c != country_col),
                    country=str(row.get(country_col, "")) if country_col else "",
                    period=str(row["period"]),
                    period_type=classify_period(str(row["period"])),
                    value=float(row["value"]),
                    unit=unit_map.get(unit_code, unit_code),
                    dimensions=dims,
                )
            )
        return observations


@register
class BisCollector(BaseCollector):
    name = "bis"
    collection = "bis"
    description = (
        "BIS Total Credit (WS_TC) + debt-service ratios (WS_DSR) + debt securities by "
        "maturity (WS_NA_SEC_DSS), quarterly"
    )

    async def collect(self) -> CollectResult:
        parser = BisParser()
        parts: list[str] = []
        total = 0
        for flow in FLOWS:
            data = await self.http.get_bytes(BULK_URL.format(flow=flow))
            observations = await asyncio.to_thread(parser.parse, flow, data)
            total += await self.upsert(observations)
            parts.append(f"{flow}: {len(observations)} obs")
        return CollectResult(source=self.name, status="ok", n_docs=total, detail="; ".join(parts))
