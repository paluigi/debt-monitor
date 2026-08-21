"""FI disclosures: EDGAR full-text search 8-K earnings discovery + FMP
transcripts (dossier 10).

sec.gov hosts require a full Chrome user agent (handled by the HTTP client).
www.sec.gov document bodies are blocked from some egress IPs — only the
keyless data APIs (efts/data.sec.gov) are used, so no proxy is needed.
"""

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

import httpx

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult

FTS_URL = "https://efts.sec.gov/LATEST/search-index"
FMP_URL = "https://financialmodelingprep.com/stable/earning-call-transcript"
FTS_QUERY = '"provision for credit losses"'

# US-listed + ADR financial institutions tracked for earnings-call signals.
TICKERS: tuple[str, ...] = (
    "JPM",
    "BAC",
    "C",
    "WFC",
    "GS",
    "MS",
    "SCHW",
    "AXP",
    "DB",
    "UBS",
    "HSBC",
    "BCS",
    "SAN",
    "BBVA",
    "TD",
    "RY",
    "ITUB",
    "BBD",
)


@register
class FiFilingsCollector(BaseCollector):
    name = "fi_filings"
    collection = "fi_filings"
    description = "EDGAR 8-K earnings-call filings discovery + FMP transcripts, daily"

    async def collect(self) -> CollectResult:
        parts: list[str] = []
        failures: list[str] = []
        total = 0
        fetched_at = datetime.now(UTC)

        # --- EDGAR FTS: recent earnings-related 8-Ks -----------------------
        end = datetime.now(UTC).date()
        start = end - timedelta(days=14)
        try:
            payload = await self.http.get_json(
                FTS_URL,
                params={
                    "q": FTS_QUERY,
                    "forms": "8-K",
                    "startdt": start.isoformat(),
                    "enddt": end.isoformat(),
                },
                timeout=60.0,
            )
            hits = payload.get("hits", {}).get("hits", [])
            docs = []
            for hit in hits:
                adsh = hit.get("_id", "")
                source = hit.get("_source", {})
                docs.append(
                    {
                        "_id": hashlib.sha256(adsh.encode()).hexdigest(),
                        "source": "fi_filings",
                        "dataset": "edgar_fts_8k",
                        "adsh": adsh,
                        "file_date": source.get("file_date", ""),
                        "tickers": source.get("display_names", []),
                        "sics": source.get("sics", []),
                        "file_type": source.get("file_type", ""),
                        "items": source.get("items", ""),
                        "fetched_at": fetched_at,
                    }
                )
            total += await self.repo.upsert_docs(self.collection, docs)
            parts.append(f"edgar_fts: {len(docs)}")
        except Exception as exc:
            failures.append(f"edgar_fts: {type(exc).__name__}: {exc}")

        # --- FMP transcripts -----------------------------------------------
        # As of 2026-08 transcripts sit behind paid plans (HTTP 402 "Restricted
        # Endpoint"); the check below degrades to a skip note instead of one
        # failure per ticker, and resumes automatically if the plan changes.
        if not self.settings.fmp_api_key:
            parts.append("fmp: skipped (no key)")
        else:
            n_transcripts = 0
            for ticker in TICKERS:
                try:
                    items = await self.http.get_json(
                        FMP_URL,
                        params={
                            "symbol": ticker,
                            "apikey": self.settings.fmp_api_key,
                        },
                        timeout=60.0,
                    )
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (402, 403):
                        parts.append("fmp: not available on current plan (402/403)")
                        break
                    failures.append(f"fmp {ticker}: HTTP {exc.response.status_code}")
                    continue
                except Exception as exc:
                    failures.append(f"fmp {ticker}: {type(exc).__name__}")
                    continue
                docs = []
                for item in items or []:
                    year = item.get("year")
                    quarter = item.get("quarter")
                    if not (year and quarter):
                        continue
                    doc_id = hashlib.sha256(f"{ticker}|{year}|{quarter}".encode()).hexdigest()
                    existing = await self.repo.find_one(
                        self.collection, {"_id": doc_id, "dataset": "fmp_transcript"}
                    )
                    if existing:
                        continue
                    docs.append(
                        {
                            "_id": doc_id,
                            "source": "fi_filings",
                            "dataset": "fmp_transcript",
                            "ticker": ticker,
                            "year": year,
                            "quarter": quarter,
                            "date": item.get("date", ""),
                            "content": item.get("content", item.get("transcriptText", "")),
                            "fetched_at": fetched_at,
                        }
                    )
                n_transcripts += await self.repo.upsert_docs(self.collection, docs)
                await asyncio.sleep(0.4)
            parts.append(f"fmp: {n_transcripts} new transcripts")

        status = "failed" if not parts else "ok"
        return CollectResult(
            source=self.name,
            status=status,
            n_docs=total,
            detail="; ".join(parts + [f"FAILED {x}" for x in failures]),
        )
