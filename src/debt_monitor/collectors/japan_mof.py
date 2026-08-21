"""Japan MoF JGB coupon-par yields: current month + historical, Shift-JIS.

The CSVs are Shift-JIS encoded with unpadded `YYYY/M/D` dates; the current-month
file is stitched on top of the historical file (dossier 06).
"""

import asyncio
import csv
import io
import re
from datetime import datetime

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult

CURRENT_URL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"
HISTORY_URL = (
    "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
)
KEEP_DAYS = 90
_MATURITY = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:Y|Year|Years|年)$", re.I)


def _maturity_label(header: str) -> str | None:
    match = _MATURITY.match(header.strip())
    return f"{float(match.group(1)):g}Y" if match else None


def parse_jgbc_csv(text: str) -> dict[str, dict[str, float]]:
    """Return {date_iso: {maturity: yield}} from one MoF CSV."""
    curves: dict[str, dict[str, float]] = {}
    reader = csv.reader(io.StringIO(text))
    header: list[str] | None = None
    maturities: list[str] = []
    for row in reader:
        if not row:
            continue
        if header is None:
            labels = [_maturity_label(cell) for cell in row[1:]]
            if any(labels):
                header = row
                maturities = [label or "" for label in labels]
                continue
        try:
            period = datetime.strptime(row[0].strip(), "%Y/%m/%d").strftime("%Y-%m-%d")
        except ValueError:
            continue
        points: dict[str, float] = {}
        for label, cell in zip(maturities, row[1:], strict=False):
            if not label:
                continue
            try:
                points[label] = float(cell)
            except TypeError, ValueError:
                continue
        if points:
            curves[period] = points
    return curves


@register
class JapanMofCollector(BaseCollector):
    name = "japan_mof"
    collection = "japan_mof"
    description = "Japan MoF JGB yield curve, daily (SJIS CSV, stitched)"

    async def collect(self) -> CollectResult:
        history_text = (await self.http.get_bytes(HISTORY_URL, timeout=90.0)).decode(
            "shift_jis", errors="replace"
        )
        current_text = (await self.http.get_bytes(CURRENT_URL)).decode(
            "shift_jis", errors="replace"
        )

        curves = await asyncio.to_thread(parse_jgbc_csv, history_text)
        curves.update(await asyncio.to_thread(parse_jgbc_csv, current_text))

        latest = sorted(curves)[-KEEP_DAYS:]
        observations = [
            self.obs(
                dataset="jgb_cme",
                series=maturity,
                country="JP",
                period=period,
                period_type="day",
                value=value,
                unit="percent",
            )
            for period in latest
            for maturity, value in curves[period].items()
        ]
        n = await self.upsert(observations)
        last_day = latest[-1] if latest else "-"
        return CollectResult(
            source=self.name,
            status="ok",
            n_docs=n,
            detail=f"{len(observations)} points over {len(latest)} days, last {last_day}",
        )
