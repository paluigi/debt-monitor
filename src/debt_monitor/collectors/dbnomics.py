"""DBnomics mirrors: Fed Z.1 / H.8, IMF IFS, ECB SUP, IMF FSI.

DBnomics is keyless but mirror-lagged (BIS ~3 quarters, IFS ~13 months) — used
here only for series without a practical upstream API path (dossier 01/03/04).
Batch endpoint `/v22/series?series_ids=...` fetches observations for many series
at once; the IMF/FSI NPL universe is discovered dynamically and re-harvested
(the same logic as scripts/acquire_npl.py, now landing in MongoDB).
"""

import asyncio
import re

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult, Observation, classify_period

BASE = "https://api.db.nomics.world/v22"
BATCH_SIZE = 20
FSI_SERIES_RE = re.compile(r"^[AQ]\.[A-Z]{2}\.FSANL_PT$")

# (dataset, series_code, country, label)
STATIC_SERIES: tuple[tuple[str, str, str, str], ...] = (
    ("FED/Z1", "FL153165105.Q", "US", "Household mortgages, level"),
    ("FED/Z1", "FL153166000.Q", "US", "Household consumer credit, level"),
    ("FED/Z1", "FL104104005.Q", "US", "NFC corporate bonds, level"),
    ("FED/Z1", "FL104190005.Q", "US", "NFC loans, level"),
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
    description = "DBnomics mirrors: Fed Z.1/H.8, IMF IFS+CPI, ECB SUP NPE, IMF FSI NPL"

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
                    if value is None:
                        continue
                    observations.append(
                        self.obs(
                            dataset=dataset,
                            series=code,
                            country=country,
                            period=str(period),
                            period_type=classify_period(str(period)),
                            value=float(value),
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
