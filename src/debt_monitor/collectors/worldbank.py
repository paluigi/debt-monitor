"""World Bank API: bank NPL ratio + central-government revenue (annual).

Documented breadth fallbacks (dossiers 04/11) — quarterly cadence comes from
IMF FSI via the dbnomics collector; the revenue indicator is CENTRAL government
(general-government revenue for the metrics layer comes from Eurostat/OECD T12).
"""

import asyncio

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult, Observation

WB_BASE = "https://api.worldbank.org/v2/country/all/indicator"
PER_PAGE = 1_500

# (indicator, dataset, unit, label) — GC.REV has no interest counterpart (dossier 11).
INDICATORS: tuple[tuple[str, str, str, str], ...] = (
    ("FB.AST.NPER.ZS", "WDI_NPL", "% of gross loans", "Bank NPL ratio"),
    ("GC.REV.XGRT.GD.ZS", "WDI_GOV", "% of GDP", "Central government revenue incl. grants"),
)


@register
class WorldBankCollector(BaseCollector):
    name = "worldbank"
    collection = "worldbank"
    description = "World Bank: NPL ratio + central-gov revenue %GDP, annual, ~200 economies"

    async def collect(self) -> CollectResult:
        observations: list[Observation] = []
        parts: list[str] = []
        for indicator, dataset, unit, label in INDICATORS:
            n_ind = await self._harvest(indicator, dataset, unit, label, observations)
            parts.append(f"{indicator}: {n_ind}")
        total = await self.upsert(observations)
        return CollectResult(
            source=self.name,
            status="ok",
            n_docs=total,
            detail="; ".join(parts),
        )

    async def _harvest(
        self, indicator: str, dataset: str, unit: str, label: str, sink: list[Observation]
    ) -> int:
        page = 1
        added = 0
        while True:
            payload = await self.http.get_json(
                f"{WB_BASE}/{indicator}",
                params={"format": "json", "per_page": PER_PAGE, "page": page},
                timeout=60.0,
            )
            if len(payload) < 2 or payload[1] is None:
                break
            for rec in payload[1]:
                if rec.get("value") is None:
                    continue
                sink.append(
                    self.obs(
                        dataset=dataset,
                        series=indicator,
                        country=rec.get("countryiso3code", ""),
                        period=str(rec.get("date", "")),
                        period_type="year",
                        value=float(rec["value"]),
                        unit=unit,
                        dimensions={
                            "country_name": rec.get("country", {}).get("value", ""),
                            "label": label,
                        },
                    )
                )
                added += 1
            meta = payload[0]
            if page * meta.get("per_page", 0) >= meta.get("total", 0):
                break
            page += 1
            await asyncio.sleep(0.3)
        return added
