"""World Bank API: bank non-performing loans ratio (annual, all economies).

Documented breadth fallback (dossier 04) — quarterly cadence comes from IMF FSI
via the dbnomics collector.
"""

import asyncio

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult, Observation

WB_URL = "https://api.worldbank.org/v2/country/all/indicator/FB.AST.NPER.ZS"
PER_PAGE = 1_500


@register
class WorldBankCollector(BaseCollector):
    name = "worldbank"
    collection = "worldbank"
    description = "World Bank NPL ratio, annual, ~200 economies"

    async def collect(self) -> CollectResult:
        observations: list[Observation] = []
        page = 1
        while True:
            payload = await self.http.get_json(
                WB_URL,
                params={"format": "json", "per_page": PER_PAGE, "page": page},
                timeout=60.0,
            )
            if len(payload) < 2 or payload[1] is None:
                break
            for rec in payload[1]:
                if rec.get("value") is None:
                    continue
                observations.append(
                    self.obs(
                        dataset="WDI_NPL",
                        series="FB.AST.NPER.ZS",
                        country=rec.get("countryiso3code", ""),
                        period=str(rec.get("date", "")),
                        period_type="year",
                        value=float(rec["value"]),
                        unit="% of gross loans",
                        dimensions={"country_name": rec.get("country", {}).get("value", "")},
                    )
                )
            meta = payload[0]
            if page * meta.get("per_page", 0) >= meta.get("total", 0):
                break
            page += 1
            await asyncio.sleep(0.3)

        total = await self.upsert(observations)
        return CollectResult(
            source=self.name,
            status="ok",
            n_docs=total,
            detail=f"{len(observations)} obs, {len({o.country for o in observations})} economies",
        )
