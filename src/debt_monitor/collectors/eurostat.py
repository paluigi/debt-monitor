"""Eurostat JSON-stat 2.0: HICP (prc_hicp_minr) + EDP Maastricht debt.

ECOICOP v2 break (dossier 05): since 2026-01 the monthly HICP dataset is
`prc_hicp_minr` with dimension `coicop18` and all-items code `TOTAL` — the v1
datasets and the ECB ICP mirror are frozen at 2025-12. JSON-stat values are
keyed by flattened multi-dimension positions, so a proper dimension-index
decoder is used (naive tail reads return false nulls).
"""

import asyncio
from itertools import product

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult

API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

HICP_DATASET = "prc_hicp_minr"
HICP_GEOS = ("EA", "DE", "FR", "IT", "ES")
HICP_UNITS = ("RCH_A", "I25")  # annual rate of change, 2021=100-style index
HICP_SINCE = "2019-01"

EDP_DATASET = "gov_10dd_edpt1"
EDP_GEOS = (
    "EA20",
    "EU27_2020",
    "DE",
    "FR",
    "IT",
    "ES",
    "NL",
    "BE",
    "AT",
    "PT",
    "IE",
    "EL",
    "FI",
    "SK",
    "SI",
    "LT",
    "LV",
    "EE",
    "LU",
    "MT",
    "CY",
    "HR",
)
EDP_SINCE = "2015"


def parse_jsonstat(js: dict) -> list[dict]:
    """Decode JSON-stat 2.0 `value` into [{coords}, value] pairs."""
    ids: list[str] = js["id"]
    sizes: list[int] = js["size"]
    codes_per_dim: list[list[str]] = []
    for dim_id in ids:
        index = js["dimension"][dim_id]["category"]["index"]
        inv = {pos: code for code, pos in index.items()}
        codes_per_dim.append([inv[i] for i in range(sizes[ids.index(dim_id)])])
    values = js.get("value", {})
    out = []
    for flat_pos, combo in enumerate(product(*codes_per_dim)):
        raw = values.get(str(flat_pos))
        if raw is None:
            continue
        coords = dict(zip(ids, combo, strict=True))
        out.append((coords, float(raw)))
    return out


@register
class EurostatCollector(BaseCollector):
    name = "eurostat"
    collection = "eurostat"
    description = "Eurostat HICP monthly (ECOICOP v2) + EDP Maastricht gov debt annual"

    async def collect(self) -> CollectResult:
        parts: list[str] = []
        failures: list[str] = []
        total = 0

        for geo in HICP_GEOS:
            for unit in HICP_UNITS:
                try:
                    js = await self.http.get_json(
                        f"{API}/{HICP_DATASET}",
                        params={
                            "format": "JSON",
                            "lang": "EN",
                            "freq": "M",
                            "coicop18": "TOTAL",
                            "geo": geo,
                            "unit": unit,
                            "sinceTimePeriod": HICP_SINCE,
                        },
                    )
                    observations = [
                        self.obs(
                            dataset=HICP_DATASET,
                            series=f"TOTAL_{unit}",
                            country=geo,
                            period=coords["time"],
                            period_type="month",
                            value=value,
                            unit=unit,
                        )
                        for coords, value in parse_jsonstat(js)
                    ]
                    n = await self.upsert(observations)
                    total += n
                    parts.append(f"HICP {geo}/{unit}: {len(observations)}")
                except Exception as exc:
                    failures.append(f"HICP {geo}/{unit}: {type(exc).__name__}")
                await asyncio.sleep(0.3)

        for geo in EDP_GEOS:
            try:
                js = await self.http.get_json(
                    f"{API}/{EDP_DATASET}",
                    params={
                        "format": "JSON",
                        "lang": "EN",
                        "na_item": "GD",
                        "sector": "S13",
                        "unit": "PC_GDP",
                        "geo": geo,
                        "sinceTimePeriod": EDP_SINCE,
                    },
                )
                observations = [
                    self.obs(
                        dataset=EDP_DATASET,
                        series="GD_PC_GDP",
                        country=geo,
                        period=coords["time"],
                        period_type="year",
                        value=value,
                        unit="PC_GDP",
                    )
                    for coords, value in parse_jsonstat(js)
                ]
                n = await self.upsert(observations)
                total += n
                parts.append(f"EDP {geo}: {len(observations)}")
            except Exception as exc:
                failures.append(f"EDP {geo}: {type(exc).__name__}")
            await asyncio.sleep(0.3)

        status = "failed" if not parts else "ok"
        return CollectResult(
            source=self.name,
            status=status,
            n_docs=total,
            detail="; ".join(parts + [f"FAILED {x}" for x in failures]),
        )
