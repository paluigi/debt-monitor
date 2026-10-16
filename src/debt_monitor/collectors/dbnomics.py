"""DBnomics mirrors: Fed Z.1 / H.8, IMF IFS, ECB SUP, IMF FSI, ONS UKEA, OECD T12.

DBnomics is keyless but mirror-lagged (BIS ~3 quarters, IFS ~13 months) — used
here only for series without a practical upstream API path (dossier 01/03/04/11).
Batch endpoint `/v22/series?series_ids=...` fetches observations for many series
at once; the IMF/FSI NPL universe and OECD T12 gov interest/revenue series are
discovered dynamically and re-harvested.
"""

import asyncio
import re

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult, Observation, classify_period

BASE = "https://api.db.nomics.world/v22"
BATCH_SIZE = 20
FSI_SERIES_RE = re.compile(r"^[AQ]\.[A-Z]{2}\.FSANL_PT$")
# OECD National Accounts table 12: A.{CTY}.S13._Z.{C=revenue|D=expenditure}.{OTR|D41}...
OECD_T12_RE = re.compile(r"^A\.([A-Z]{3})\.S13\._Z\.[CD]\.(OTR|D41)\._Z\._Z\.XDC\.S\.V\.N\.T0200$")
OECD_T12_DATASETS = ("OECD/DSD_NASEC10@DF_TABLE12", "OECD/DSD_NASEC10@DF_TABLE12_EXP")

# (dataset, series_code, country, label)
STATIC_SERIES: tuple[tuple[str, str, str, str], ...] = (
    ("FED/Z1", "FL153165105.Q", "US", "Household mortgages, level"),
    ("FED/Z1", "FL153166000.Q", "US", "Household consumer credit, level"),
    ("FED/Z1", "FL104104005.Q", "US", "NFC corporate bonds, level"),
    ("FED/Z1", "FL104190005.Q", "US", "NFC loans, level"),
    # Metrics-layer inputs (dossier 11): interest paid by sector, SAAR $mn.
    ("FED/Z1", "FA156130005.Q", "US", "Households & NPISH interest paid (computed)"),
    ("FED/Z1", "FA106130001.Q", "US", "NFC interest paid (NIPA input)"),
    ("FED/Z1", "FA106130003.Q", "US", "NFC interest paid (zero-seasonal input)"),
    ("FED/Z1", "FA366130005.Q", "US", "General government interest paid (computed)"),
    # UK sector accounts via the ONS mirror (indexed fresh; dossier 11).
    ("ONS/UKEA", "HABN.Q", "GB", "Households gross disposable income B6g, CP GBP mn NSA"),
    ("ONS/UKEA", "HAAJ.Q", "GB", "NPISH gross disposable income B6g, CP GBP mn NSA"),
    ("ONS/UKEA", "HACY.Q", "GB", "Households interest D.41 uses, GBP mn NSA"),
    ("ONS/UKEA", "EABG.Q", "GB", "NFC interest D.41 uses, GBP mn NSA"),
    ("ONS/UKEA", "I69W.Q", "GB", "Central gov total interest paid excl FISIM, GBP mn"),
    ("ONS/UKEA", "I69X.Q", "GB", "Local gov total interest paid excl FISIM, GBP mn"),
    ("ONS/UKEA", "CGBZ.Q", "GB", "Gross operating surplus of corporations, SA GBP mn"),
    ("FED/H8", "B1001NCBA", "US", "Commercial bank credit"),
    ("IMF/IFS", "M.CN.PCPI_IX", "CN", "CPI index"),
    ("IMF/IFS", "M.CN.32D___XDC", "CN", "Claims on private sector"),
    ("IMF/IFS", "Q.GB.NGDP_SA_XDC", "GB", "Nominal GDP, SA"),
    ("IMF/IFS", "Q.JP.NGDP_SA_XDC", "JP", "Nominal GDP, SA"),
    ("IMF/IFS", "Q.IN.NGDP_SA_XDC", "IN", "Nominal GDP, SA"),
    ("IMF/IFS", "Q.US.NGDP_SA_XDC", "US", "Nominal GDP, SA"),
    ("IMF/IFS", "Q.DE.NGDP_SA_XDC", "DE", "Nominal GDP, SA"),
    ("IMF/IFS", "A.CN.NGDP_XDC", "CN", "Nominal GDP, annual"),
    ("ECB/SUP", "Q.DE.W0.S11.E0035._T.ALL._Z.N_.LE.E.C", "DE", "NPE stock, NFC"),
    ("ECB/SUP", "Q.DE.W0.S11.E0036._T.ALL._Z.N_.LE.E.C", "DE", "New NPE flows, NFC"),
)


@register
class DbnomicsCollector(BaseCollector):
    name = "dbnomics"
    collection = "dbnomics"
    description = "DBnomics mirrors: Fed Z.1/H.8, IMF IFS+CPI, ECB SUP NPE, IMF FSI NPL, ONS UKEA, OECD T12 gov accounts"

    async def collect(self) -> CollectResult:
        parts: list[str] = []
        total = 0

        # 1) curated static series (batched)
        static_ids = [
            (dataset, code, country, label) for dataset, code, country, label in STATIC_SERIES
        ]
        docs = await self._fetch_batches(static_ids)
        total += await self.upsert(docs)
        parts.append(f"static: {len(docs)} obs")

        # 2) IMF/FSI NPL — discover all FSANL_PT series, then batch-fetch
        fsi_series = await self._list_fsi_npl_series()
        fsi_docs = await self._fetch_batches(fsi_series)
        total += await self.upsert(fsi_docs)
        parts.append(f"FSI: {len(fsi_docs)} obs / {len(fsi_series)} series")

        # 3) OECD T12 — general gov interest (D41) + total revenue (OTR), annual
        t12_series = await self._list_oecd_t12_series()
        t12_docs = await self._fetch_batches(t12_series)
        total += await self.upsert(t12_docs)
        parts.append(f"OECD_T12: {len(t12_docs)} obs / {len(t12_series)} series")

        return CollectResult(source=self.name, status="ok", n_docs=total, detail="; ".join(parts))

    async def _fetch_batches(self, series_list) -> list[Observation]:
        """Batch-fetch observations; `series_list` is (dataset, code, country, label)."""
        observations: list[Observation] = []
        for i in range(0, len(series_list), BATCH_SIZE):
            batch = series_list[i : i + BATCH_SIZE]
            ids = ",".join(f"{d}/{c}" for d, c, _, _ in batch)
            payload = await self.http.get_json(
                f"{BASE}/series",
                params={"series_ids": ids, "observations": 1, "format": "json"},
                timeout=90.0,
            )
            by_code = {code: (dataset, country, label) for dataset, code, country, label in batch}
            for doc in payload.get("series", {}).get("docs", []):
                code = doc.get("series_code", "")
                dataset, country, label = by_code.get(code, (code, "", ""))
                for period, value in zip(doc.get("period", []), doc.get("value", []), strict=False):
                    # ONS mirror rows carry 'NA' strings for missing values.
                    if value is None or isinstance(value, str) and value.strip().upper() in ("NA", "", "-"):
                        continue
                    try:
                        numeric = float(value)
                    except (TypeError, ValueError):
                        continue
                    observations.append(
                        self.obs(
                            dataset=dataset,
                            series=code,
                            country=country,
                            period=str(period),
                            period_type=classify_period(str(period)),
                            value=numeric,
                            unit="native",
                            dimensions={"series_name": doc.get("series_name", label)},
                        )
                    )
            await asyncio.sleep(0.4)
        return observations

    async def _list_fsi_npl_series(self) -> list[tuple[str, str, str, str]]:
        """Return (dataset, code, country, label) for every FSI NPL series."""
        out: list[tuple[str, str, str, str]] = []
        offset = 0
        while True:
            payload = await self.http.get_json(
                f"{BASE}/series/IMF/FSI",
                params={
                    "q": "FSANL_PT",
                    "limit": 100,
                    "offset": offset,
                    "observations": 0,
                    "format": "json",
                },
                timeout=90.0,
            )
            docs = payload.get("series", {}).get("docs", [])
            for d in docs:
                code = d.get("series_code", "")
                name = d.get("series_name", "")
                if FSI_SERIES_RE.match(code):
                    country = name.split("–")[1].strip() if "–" in name else code.split(".")[1]
                    out.append(("IMF/FSI", code, country, name))
            if len(docs) < 100:
                return out
            offset += 100
            await asyncio.sleep(0.2)

    async def _list_oecd_t12_series(self) -> list[tuple[str, str, str, str]]:
        """Return (dataset, code, country, label) for OECD T12 gov interest/revenue.

        Series grammar (dossier 11): A.{COUNTRY}.S13._Z.{C|D}.{OTR|D41}._Z._Z.XDC.S.V.N.T0200
        — searched per keyword since the dataset endpoint has no code filter.
        """
        out: list[tuple[str, str, str, str]] = []
        seen: set[tuple[str, str]] = set()
        for dataset in OECD_T12_DATASETS:
            for q in ("interest", "Total government revenue"):
                offset = 0
                while True:
                    payload = await self.http.get_json(
                        f"{BASE}/series/{dataset}",
                        params={
                            "q": q,
                            "limit": 100,
                            "offset": offset,
                            "observations": 0,
                            "format": "json",
                        },
                        timeout=90.0,
                    )
                    docs = payload.get("series", {}).get("docs", [])
                    for d in docs:
                        code = d.get("series_code", "")
                        m = OECD_T12_RE.match(code)
                        if m and (dataset, code) not in seen:
                            seen.add((dataset, code))
                            out.append((dataset, code, m.group(1), d.get("series_name", "")))
                    if len(docs) < 100:
                        break
                    offset += 100
                    await asyncio.sleep(0.2)
                await asyncio.sleep(0.2)
        return out
