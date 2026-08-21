"""ECB data-api SDMX-CSV: BSI, QSA, YC, MIR, HICP.

Key semantics from dossier 03/06: EA MFI-loan aggregates need CURRENCY_TRANS
`Z01`; EA sector-account aggregates are REF_AREA `I9` (not `U2`); yield-curve
`G_N_A` is the AAA-only curve and `G_N_C` all ratings; YC queries need a long
timeout. The euro-corporate-yields flow does not exist (dossier 06) — EUR
corporate stress comes from FRED ICE BofA OAS instead.

HICP: the old ICP flow is frozen at 2025-12 (ECOICOP v2 break, dossier 05).
Its successor on the ECB portal is the `HICP` flow with a 7-segment key
`M.{REF_AREA}.N.{ITEM}.{DATA_PROVIDER}.{SUFFIX}` — all-items stays `000000`,
annual rate `4D0.ANR`, index `4D0.INX`; verified current through 2026-07 with
values matching Eurostat prc_hicp_minr. Partial/prefix keys on this flow (and
the whole QSA flow) trip the portal WAF — always request full series keys.

Known issue (2026-08-20): the ECB portal WAF serves "access blocked" (HTTP 400)
for /service/data/QSA/* from some networks — including ours, for every UA and
client, while BSI/MIR/YC stay open. The QSA keys below are kept in rotation so
the daily run picks the flow back up automatically if the block lifts; EA
sector stocks are meanwhile covered by BIS WS_TC.
"""

import asyncio
import io

import polars as pl

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult, Observation

DATA_API = "https://data-api.ecb.europa.eu/service/data"

_YC_MATURITIES = (
    "SR_3M",
    "SR_6M",
    "SR_1Y",
    "SR_2Y",
    "SR_5Y",
    "SR_7Y",
    "SR_10Y",
    "SR_15Y",
    "SR_20Y",
    "SR_30Y",
)

# (flow, key, last_n, country, timeout, extra dims)
KEYS: tuple[tuple[str, str, int, str, float, dict], ...] = (
    # BSI — monthly MFI loans by sector (EA aggregates use Z01 = all currencies)
    ("BSI", "M.U2.N.U.A20.A.1.U2.2250.Z01.E", 13, "EA", 60.0, {"sector": "households"}),
    (
        "BSI",
        "M.U2.N.U.A22.A.1.U2.2250.Z01.E",
        13,
        "EA",
        60.0,
        {"sector": "households_house_purchase"},
    ),
    (
        "BSI",
        "M.U2.N.U.A21.A.1.U2.2250.Z01.E",
        13,
        "EA",
        60.0,
        {"sector": "households_consumer_credit"},
    ),
    (
        "BSI",
        "M.U2.N.U.A20.A.1.U2.2240.Z01.E",
        13,
        "EA",
        60.0,
        {"sector": "non-financial corporations"},
    ),
    ("BSI", "M.DE.N.A.A20.A.1.U2.2250.EUR.E", 13, "DE", 60.0, {"sector": "households"}),
    # QSA — quarterly sector-account liability stocks (EA aggregate is I9)
    (
        "QSA",
        "Q.I9.W0.S1M.S1.N.LE.F4.T._Z.XDC._T.S.V.N._T",
        8,
        "EA",
        60.0,
        {"sector": "households", "instrument": "loans"},
    ),
    (
        "QSA",
        "Q.I9.W0.S11.S1.N.LE.F3.T._Z.XDC._T.S.V.N._T",
        8,
        "EA",
        60.0,
        {"sector": "non-financial corporations", "instrument": "debt securities"},
    ),
    (
        "QSA",
        "Q.I9.W0.S11.S1.N.LE.F4.T._Z.XDC._T.S.V.N._T",
        8,
        "EA",
        60.0,
        {"sector": "non-financial corporations", "instrument": "loans"},
    ),
    # MIR — monthly bank lending rates (EA NFC new loans)
    (
        "MIR",
        "M.U2.B.A2A.A.R.0.2240.EUR.N",
        13,
        "EA",
        60.0,
        {"sector": "non-financial corporations", "rate": "new business"},
    ),
)

YC_KEYS = tuple(
    (
        "YC",
        f"B.U2.EUR.4F.{bucket}.SV_C_YM.{mat}",
        30,
        "EA",
        90.0,
        {"rating_bucket": "AAA" if bucket == "G_N_A" else "all ratings", "maturity": mat},
    )
    for bucket in ("G_N_A", "G_N_C")
    for mat in _YC_MATURITIES
)

# HICP — ECOICOP v2 successor of the frozen ICP flow; all-items annual rate +
# index for the euro area and the large members (ECB REF_AREA codes: U2 = EA
# aggregate, GR = Greece). Cross-checked against Eurostat prc_hicp_minr.
_HICP_AREAS = ("U2", "DE", "FR", "IT", "ES", "NL")
_HICP_MEASURES = (("4D0.ANR", "annual_rate"), ("4D0.INX", "index"))
HICP_KEYS = tuple(
    (
        "HICP",
        f"M.{area}.N.000000.{suffix}",
        13,
        "EA" if area == "U2" else area,
        60.0,
        {"item": "all-items", "measure": measure},
    )
    for area in _HICP_AREAS
    for suffix, measure in _HICP_MEASURES
)

_FREQ_TO_TYPE = {"D": "day", "W": "week", "M": "month", "Q": "quarter", "B": "day", "A": "year"}


def parse_csvdata(csv_bytes: bytes, flow: str, country: str, dims: dict) -> list[Observation]:
    df = pl.read_csv(io.BytesIO(csv_bytes))
    out: list[Observation] = []
    for row in df.iter_rows(named=True):
        raw = row.get("OBS_VALUE")
        try:
            value = float(raw)
        except TypeError, ValueError:
            continue
        freq = str(row.get("FREQ", ""))
        out.append(
            Observation(
                source="ecb",
                dataset=flow,
                series=str(row.get("KEY", "")),
                country=country,
                period=str(row.get("TIME_PERIOD", "")),
                period_type=_FREQ_TO_TYPE.get(freq, "day"),
                value=value,
                unit=str(row.get("UNIT", "")),
                dimensions=dims,
            )
        )
    return out


@register
class EcbCollector(BaseCollector):
    name = "ecb"
    collection = "ecb"
    description = "ECB BSI/QSA/MIR/YC/HICP via data-api SDMX-CSV (daily-monthly-quarterly)"

    async def collect(self) -> CollectResult:
        parts: list[str] = []
        total = 0
        failures: list[str] = []
        for flow, key, last_n, country, timeout, dims in KEYS + YC_KEYS + HICP_KEYS:
            try:
                data = await self.http.get_bytes(
                    f"{DATA_API}/{flow}/{key}",
                    params={"format": "csvdata", "lastNObservations": last_n},
                    timeout=timeout,
                )
                observations = parse_csvdata(data, flow, country, dims)
            except Exception as exc:  # one dead key must not sink the rest
                failures.append(f"{flow}/{key.split('.')[0]}: {type(exc).__name__}")
                continue
            n = await self.upsert(observations)
            total += n
            parts.append(f"{flow}: {len(observations)}")
            await asyncio.sleep(0.2)
        status = "failed" if not parts else "ok"
        return CollectResult(
            source=self.name,
            status=status,
            n_docs=total,
            detail="; ".join(parts + [f"FAILED {x}" for x in failures]),
        )
