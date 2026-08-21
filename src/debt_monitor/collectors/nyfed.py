"""NY Fed Household Debt & Credit quarterly report XLSX.

The report URL pattern is mechanical: `HHD_C_Report_{YYYY}Q{n}` with no file
extension. Reports land ~5-6 weeks after quarter-end, so candidates walk back
from the current quarter. The medialibrary host answers missing files with
HTTP 200 + HTML (soft 404), so responses are validated by ZIP magic bytes
before parsing (dossier 03/08). Sheets are archived as raw rows — the analysis
layer owns layout interpretation.
"""

import asyncio
import hashlib
from datetime import UTC, datetime

import fastexcel

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult

BASE_URL = (
    "https://www.newyorkfed.org/medialibrary/interactives/householdcredit/"
    "data/xls/HHD_C_Report_{label}"
)
LOOKBACK_QUARTERS = 5
ZIP_MAGIC = b"PK\x03\x04"


def quarter_labels(today: datetime, count: int) -> list[str]:
    """Current quarter first, then stepping back `count` quarters."""
    labels: list[str] = []
    year, month = today.year, today.month
    quarter = (month - 1) // 3 + 1
    for _ in range(count):
        labels.append(f"{year}Q{quarter}")
        quarter -= 1
        if quarter == 0:
            quarter, year = 4, year - 1
    return labels


def parse_hhdc_xlsx(data: bytes, label: str, fetched_at: datetime) -> list[dict]:
    """Flatten every sheet into raw row documents keyed by sheet+row index."""
    workbook = fastexcel.read_excel(data)
    docs: list[dict] = []
    for sheet_name in workbook.sheet_names:
        frame = workbook.load_sheet_by_name(sheet_name, header_row=None)
        for row_index, row in enumerate(frame.to_polars().iter_rows()):
            cells = ["" if c is None else str(c) for c in row]
            if not any(cells):
                continue
            doc_id = hashlib.sha256(f"{label}|{sheet_name}|{row_index}".encode()).hexdigest()
            docs.append(
                {
                    "_id": doc_id,
                    "source": "nyfed",
                    "dataset": "hhdc",
                    "report_quarter": label,
                    "sheet": sheet_name,
                    "row_index": row_index,
                    "cells": cells,
                    "fetched_at": fetched_at,
                }
            )
    return docs


@register
class NyFedCollector(BaseCollector):
    name = "nyfed"
    collection = "nyfed"
    description = "NY Fed Household Debt & Credit report XLSX, quarterly (rolling URL)"

    async def collect(self) -> CollectResult:
        candidates = quarter_labels(datetime.now(UTC), LOOKBACK_QUARTERS)

        for label in candidates:
            if await self.repo.find_one(self.collection, {"report_quarter": label}):
                return CollectResult(
                    source=self.name,
                    status="skipped",
                    detail=f"report {label} already stored",
                )

        label = ""
        data = b""
        for candidate in candidates:
            fetched = await self.http.get_bytes(BASE_URL.format(label=candidate))
            if fetched.startswith(ZIP_MAGIC):
                label, data = candidate, fetched
                break
        if not label:
            return CollectResult(
                source=self.name,
                status="skipped",
                detail="no XLSX found for recent quarters (soft-404 HTML responses)",
            )

        fetched_at = datetime.now(UTC)
        docs = await asyncio.to_thread(parse_hhdc_xlsx, data, label, fetched_at)
        n = await self.repo.upsert_docs(self.collection, docs)
        return CollectResult(
            source=self.name,
            status="ok",
            n_docs=n,
            detail=f"report {label}: {len(docs)} rows across sheets",
        )
