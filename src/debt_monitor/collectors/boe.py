"""Bank of England gilt yield curves (GLC): nominal spot curve from the
latest-yield-curve-data zip. XLSX layout (dossier 06): a `years:` label row
precedes the maturity header; dates run down the first column; stale `#VALUE!`
cells must be filtered."""

import asyncio
from datetime import datetime

import fastexcel

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.http import unzip_members
from debt_monitor.models import CollectResult

ZIP_URL = (
    "https://www.bankofengland.co.uk/-/media/boe/files/statistics/"
    "yield-curves/latest-yield-curve-data.zip"
)
KEEP_ROWS = 90
_STALE = {"#VALUE!", "#N/A", ""}


def _parse_date(cell) -> str | None:
    if hasattr(cell, "strftime"):
        return cell.strftime("%Y-%m-%d")
    text = str(cell).strip()
    try:  # '2026-08-03' or '2026-08-03 00:00:00'
        return datetime.fromisoformat(text).strftime("%Y-%m-%d")
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_float(cell) -> float | None:
    try:
        return float(str(cell).strip())
    except TypeError, ValueError:
        return None


def parse_glcl_zip(data: bytes) -> list[tuple[str, str, float]]:
    """Return [(date_iso, maturity_label, yield)] from the nominal spot curve.

    Layout: the `years:` row carries the maturities in its cells (0.5, 1, ...
    25); one blank row follows; then one row per business day. The sibling
    sheet `3. spot, short end` covers only maturities < 6 months and is
    ignored.
    """
    members = unzip_members(data)
    target = next(
        (
            name
            for name in members
            if name.lower().endswith((".xlsx", ".xls"))
            and "nominal" in name.lower()
            and "daily" in name.lower()
        ),
        None,
    )
    if target is None:
        raise ValueError(f"no nominal-daily workbook in zip: {list(members)}")
    workbook = fastexcel.read_excel(members[target])
    sheet_name = next(
        (n for n in workbook.sheet_names if "spot curve" in n.lower()),
        workbook.sheet_names[0],
    )
    rows = list(workbook.load_sheet_by_name(sheet_name, header_row=None).to_polars().iter_rows())

    years_idx = next(
        (i for i, row in enumerate(rows) if str(row[0]).strip().lower() == "years:"), None
    )
    if years_idx is None or years_idx + 2 >= len(rows):
        raise ValueError("nominal spot curve layout changed: no 'years:' row")
    maturities = [f"{float(x):g}Y" for x in rows[years_idx][1:] if x is not None]

    out: list[tuple[str, str, float]] = []
    for row in rows[years_idx + 2 :]:
        period = _parse_date(row[0])
        if period is None:
            continue
        for maturity, cell in zip(maturities, row[1:], strict=False):
            if str(cell).strip() in _STALE:
                continue
            value = _parse_float(cell)
            if value is not None:
                out.append((period, maturity, value))
    return out


@register
class BoeCollector(BaseCollector):
    name = "boe"
    collection = "boe"
    description = "Bank of England nominal gilt spot curve, daily"

    async def collect(self) -> CollectResult:
        data = await self.http.get_bytes(ZIP_URL)
        points = await asyncio.to_thread(parse_glcl_zip, data)
        observations = [
            self.obs(
                dataset="glc_nominal_spot",
                series=maturity,
                country="GB",
                period=period,
                period_type="day",
                value=value,
                unit="percent",
            )
            for period, maturity, value in points
        ]
        n = await self.upsert(observations)
        return CollectResult(
            source=self.name,
            status="ok",
            n_docs=n,
            detail=f"{len(observations)} points over last {KEEP_ROWS} curve dates",
        )
