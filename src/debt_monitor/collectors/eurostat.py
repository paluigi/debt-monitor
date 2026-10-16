"""Eurostat JSON-stat 2.0: HICP (prc_hicp_minr) + EDP Maastricht debt +
quarterly sector accounts (nasq_10_nf_tr) + annual gov revenue (gov_10a_main).

ECOICOP v2 break (dossier 05): since 2026-01 the monthly HICP dataset is
`prc_hicp_minr` with dimension `coicop18` and all-items code `TOTAL` — the v1
datasets and the ECB ICP mirror are frozen at 2025-12. JSON-stat values are
keyed by flattened multi-dimension positions, so a proper dimension-index
decoder is used (naive tail reads return false nulls).

Sector accounts (dossier 11): D.41 interest payable + B6G/B2A3G incomes per
sector, quarterly through 2026-Q2. The API silently zeroes INVALID filter
values (HTTP 200, values=0) — codes below are live-pinned: EA aggregate geo is
EA21 here (not EA20), operating surplus is B2A3G (not B2G_B3G), units are
CP_MEUR/CP_MNAC and D.41 needs direct=PAID.
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

# ---- quarterly sector accounts (dossier 11) ---------------------------------
SECTOR_DATASET = "nasq_10_nf_tr"
SECTOR_GEOS = (
    "BE", "BG", "CZ", "DK", "DE", "EE", "IE", "EL", "ES", "FR", "HR", "IT",
    "CY", "LV", "LT", "LU", "HU", "MT", "NL", "AT", "PL", "PT", "RO", "SI",
    "SK", "FI", "SE", "IS", "NO", "UA",
)
SECTOR_AGGREGATE_GEOS = ("EA21", "EU27_2020")  # EA aggregate is EA21 here, in CP_MEUR only
# (na_item, sectors) — D.41 interest payable per sector + income aggregates.
SECTOR_COMBOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("D41", ("S11", "S12", "S13", "S14_S15")),
    ("B6G", ("S14_S15",)),
    ("B2A3G", ("S11", "S12")),
)
SECTOR_SINCE = "2000-Q1"

# Annual fallback for annual-only ESA reporters (Switzerland; dossier 11).
SECTOR_ANNUAL_DATASET = "nasa_10_nf_tr"
SECTOR_ANNUAL_GEOS = ("CH",)

# General government total revenue — annual only on the dissemination API
# (gov_10q_* datasets 404; freq=Q zeroed; dossier 11).
GOV_MAIN_DATASET = "gov_10a_main"
GOV_MAIN_GEOS = SECTOR_GEOS + SECTOR_AGGREGATE_GEOS + ("EA20",)
GOV_MAIN_UNITS = ("MIO_NAC", "PC_GDP")
GOV_MAIN_SINCE = "2000"

# Quarterly nominal GDP (metrics-layer denominator; resolves dossier-05 open
# item — works once unit/s_adj are pinned, same silent-zeroing trap).
GDP_DATASET = "namq_10_gdp"
GDP_GEOS = SECTOR_GEOS + SECTOR_AGGREGATE_GEOS
GDP_SINCE = "2000-Q1"


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
    description = (
        "Eurostat HICP monthly (ECOICOP v2) + EDP debt annual + sector accounts "
        "(D.41 interest, B6G/B2A3G incomes) + quarterly GDP + gov revenue annual"
    )

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

        # Quarterly sector accounts: countries in national currency, EA/EU
        # aggregates in EUR (mixed currencies make CP_MNAC meaningless there).
        for na_item, sectors in SECTOR_COMBOS:
            for geo_group, unit in ((SECTOR_GEOS, "CP_MNAC"), (SECTOR_AGGREGATE_GEOS, "CP_MEUR")):
                try:
                    js = await self.http.get_json(
                        f"{API}/{SECTOR_DATASET}",
                        params={
                            "format": "JSON",
                            "lang": "EN",
                            "freq": "Q",
                            "unit": unit,
                            "na_item": na_item,
                            "sector": list(sectors),
                            "direct": "PAID",
                            "s_adj": "NSA",
                            "geo": list(geo_group),
                            "sinceTimePeriod": SECTOR_SINCE,
                        },
                    )
                    observations = [
                        self.obs(
                            dataset=SECTOR_DATASET,
                            series=f"{na_item}_{coords['sector']}",
                            country=coords["geo"],
                            period=coords["time"],
                            value=value,
                            unit=unit,
                            dimensions={
                                "na_item": na_item,
                                "sector": coords["sector"],
                                "s_adj": "NSA",
                            },
                        )
                        for coords, value in parse_jsonstat(js)
                        if coords["sector"] in sectors
                    ]
                    n = await self.upsert(observations)
                    total += n
                    parts.append(f"SECTOR {na_item}/{unit}: {len(observations)}")
                except Exception as exc:
                    failures.append(f"SECTOR {na_item}/{unit}: {type(exc).__name__}")
                await asyncio.sleep(0.3)

        # Annual sector accounts for annual-only reporters (CH).
        for na_item, sectors in SECTOR_COMBOS:
            try:
                js = await self.http.get_json(
                    f"{API}/{SECTOR_ANNUAL_DATASET}",
                    params={
                        "format": "JSON",
                        "lang": "EN",
                        "freq": "A",
                        "unit": "CP_MNAC",
                        "na_item": na_item,
                        "sector": list(sectors),
                        "direct": "PAID",
                        "geo": list(SECTOR_ANNUAL_GEOS),
                        "sinceTimePeriod": "2000",
                    },
                )
                observations = [
                    self.obs(
                        dataset=SECTOR_ANNUAL_DATASET,
                        series=f"{na_item}_{coords['sector']}",
                        country=coords["geo"],
                        period=coords["time"],
                        value=value,
                        unit="CP_MNAC",
                        dimensions={"na_item": na_item, "sector": coords["sector"]},
                    )
                    for coords, value in parse_jsonstat(js)
                    if coords["sector"] in sectors
                ]
                n = await self.upsert(observations)
                total += n
                parts.append(f"SECTOR_A {na_item}: {len(observations)}")
            except Exception as exc:
                failures.append(f"SECTOR_A {na_item}: {type(exc).__name__}")
            await asyncio.sleep(0.3)

        # Annual general government total revenue (revenue-denominator variant).
        for unit in GOV_MAIN_UNITS:
            try:
                js = await self.http.get_json(
                    f"{API}/{GOV_MAIN_DATASET}",
                    params={
                        "format": "JSON",
                        "lang": "EN",
                        "freq": "A",
                        "unit": unit,
                        "na_item": "TR",
                        "sector": "S13",
                        "geo": list(GOV_MAIN_GEOS),
                        "sinceTimePeriod": GOV_MAIN_SINCE,
                    },
                )
                observations = [
                    self.obs(
                        dataset=GOV_MAIN_DATASET,
                        series=f"TR_{unit}",
                        country=coords["geo"],
                        period=coords["time"],
                        value=value,
                        unit=unit,
                    )
                    for coords, value in parse_jsonstat(js)
                ]
                n = await self.upsert(observations)
                total += n
                parts.append(f"GOV_TR/{unit}: {len(observations)}")
            except Exception as exc:
                failures.append(f"GOV_TR/{unit}: {type(exc).__name__}")
            await asyncio.sleep(0.3)

        # Quarterly nominal GDP, B1GQ, quarterly flow in national currency
        # (aggregates in EUR). Same unit split as the sector accounts.
        for geo_group, unit in ((SECTOR_GEOS, "CP_MNAC"), (SECTOR_AGGREGATE_GEOS, "CP_MEUR")):
            try:
                js = await self.http.get_json(
                    f"{API}/{GDP_DATASET}",
                    params={
                        "format": "JSON",
                        "lang": "EN",
                        "freq": "Q",
                        "unit": unit,
                        "s_adj": "NSA",
                        "na_item": "B1GQ",
                        "geo": list(geo_group),
                        "sinceTimePeriod": GDP_SINCE,
                    },
                )
                observations = [
                    self.obs(
                        dataset=GDP_DATASET,
                        series="B1GQ",
                        country=coords["geo"],
                        period=coords["time"],
                        value=value,
                        unit=unit,
                    )
                    for coords, value in parse_jsonstat(js)
                ]
                n = await self.upsert(observations)
                total += n
                parts.append(f"GDP/{unit}: {len(observations)}")
            except Exception as exc:
                failures.append(f"GDP/{unit}: {type(exc).__name__}")
            await asyncio.sleep(0.3)

        status = "failed" if not parts else "ok"
        return CollectResult(
            source=self.name,
            status=status,
            n_docs=total,
            detail="; ".join(parts + [f"FAILED {x}" for x in failures]),
        )
