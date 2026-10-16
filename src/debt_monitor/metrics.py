"""Derived debt-burden metrics from the collected observations.

Three metrics per actor (ESA2010 sectors) and country:

- ``interest_to_income``      (M1): sector interest payable / sector income
- ``debt_service_to_income``  (M2): BIS DSR for households & NFCs (interest +
  amortisation, as published); for government: (interest + debt securities
  maturing within 1 year) / income — a rollover-risk proxy, securities only.
- ``debt_to_income``          (M3): end-of-period debt stock / trailing income.

Government income has two denominator variants: ``gdp`` and
``government_revenue``. Financial corporations get interest/income only (debt
levels are interbank-contaminated; no principal data exists).

Alignment conventions (dossier 11):
- Eurostat / ONS / IMF-IFS quarterly flows are NOT annualized -> income and
  interest are trailing-4-quarter sums (TTM); stocks are end-of-quarter levels.
- FRED/BEA and Fed Z.1 values are SAAR annual rates -> used as-is.
- Annual-only inputs (OECD T12, WEO, Eurostat gov_10a_main) produce annual rows
  only; no interpolation, no estimation. All ratios are percent.
- Units are normalised to national-currency BILLIONS per year before pairing.
"""

import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from debt_monitor.db import MongoRepository

logger = logging.getLogger(__name__)

M_INTEREST = "interest_to_income"
M_SERVICE = "debt_service_to_income"
M_DEBT = "debt_to_income"

HH = "households"
NFC = "non_financial_corporations"
FC = "financial_corporations"
GOV = "government"

EU_GEOS = (
    "BE", "BG", "CZ", "DK", "DE", "EE", "IE", "EL", "ES", "FR", "HR", "IT",
    "CY", "LV", "LT", "LU", "HU", "MT", "NL", "AT", "PL", "PT", "RO", "SI",
    "SK", "FI", "SE", "IS", "NO", "UA",
)
AGG_GEOS = ("EA21", "EU27_2020")

# ISO2 -> currency (BIS reporting set + euro-area aggregates).
CURRENCY: dict[str, str] = {
    "US": "USD", "GB": "GBP", "JP": "JPY", "CN": "CNY", "IN": "INR", "SE": "SEK",
    "DK": "DKK", "PL": "PLN", "CZ": "CZK", "HU": "HUF", "RO": "RON", "NO": "NOK",
    "CH": "CHF", "IS": "ISK", "UA": "UAH", "KR": "KRW", "AU": "AUD", "CA": "CAD",
    "MX": "MXN", "TR": "TRY", "ZA": "ZAR", "BR": "BRL", "HK": "HKD", "SG": "SGD",
    "ID": "IDR", "MY": "MYR", "TH": "THB", "PH": "PHP", "TW": "TWD", "AR": "ARS",
    "CL": "CLP", "CO": "COP", "IL": "ILS", "NZ": "NZD", "PE": "PEN", "PK": "PKR",
    "RU": "RUB", "SA": "SAR", "LB": "LBP", "BG": "EUR",
    "XM": "EUR", "U2": "EUR", "EA21": "EUR", "EU27_2020": "EUR", "EA20": "EUR",
    "DE": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR", "NL": "EUR", "BE": "EUR",
    "AT": "EUR", "PT": "EUR", "IE": "EUR", "EL": "EUR", "FI": "EUR", "SK": "EUR",
    "SI": "EUR", "LT": "EUR", "LV": "EUR", "EE": "EUR", "LU": "EUR", "MT": "EUR",
    "CY": "EUR", "HR": "EUR",
}

# ISO3 -> ISO2 for OECD T12 / WEO / WDI reporting countries.
ISO3_TO_2: dict[str, str] = {
    "USA": "US", "GBR": "GB", "JPN": "JP", "CHN": "CN", "IND": "IN",
    "DEU": "DE", "FRA": "FR", "ITA": "IT", "ESP": "ES", "NLD": "NL",
    "BEL": "BE", "AUT": "AT", "PRT": "PT", "IRL": "IE", "GRC": "EL",
    "FIN": "FI", "SVK": "SK", "SVN": "SI", "LTU": "LT", "LVA": "LV",
    "EST": "EE", "LUX": "LU", "MLT": "MT", "CYP": "CY", "HRV": "HR",
    "BGR": "BG", "SWE": "SE", "DNK": "DK", "POL": "PL", "CZE": "CZ",
    "HUN": "HU", "ROU": "RO", "NOR": "NO", "CHE": "CH", "ISL": "IS",
    "UKR": "UA", "KOR": "KR", "AUS": "AU", "CAN": "CA", "MEX": "MX",
    "TUR": "TR", "ZAF": "ZA", "BRA": "BR", "HKG": "HK", "SGP": "SG",
    "IDN": "ID", "MYS": "MY", "THA": "TH", "PHL": "PH", "TWN": "TW",
    "ARG": "AR", "CHL": "CL", "COL": "CO", "ISR": "IL", "NZL": "NZ",
    "PER": "PE", "PAK": "PK", "RUS": "RU", "SAU": "SA", "LBN": "LB",
    "CRI": "CR", "URY": "UY", "EGY": "EG", "MAR": "MA", "VNM": "VN",
}


# ---------------------------------------------------------------- helpers ----
def qkey(period: str) -> tuple[int, int] | None:
    """'2026-Q2' -> (2026, 2); None for non-quarters."""
    if "-Q" not in period:
        return None
    year, quarter = period.split("-Q")
    return int(year), int(quarter)


def prev_quarters(period: str, n: int = 4) -> list[str]:
    y, q = qkey(period)  # type: ignore[misc]
    out = []
    for i in range(n):
        total = y * 4 + (q - 1) - i
        out.append(f"{total // 4:04d}-Q{total % 4 + 1}")
    return out


def ttm(index: dict[str, float], period: str) -> float | None:
    """Trailing-4-quarter sum of a non-annualized quarterly flow."""
    if qkey(period) is None:
        return None
    vals = [index.get(p) for p in prev_quarters(period, 4)]
    if any(v is None for v in vals):
        return None
    return float(sum(vals))  # type: ignore[arg-type]


def annual_of_quarters(index: dict[str, float], year: int) -> float | None:
    vals = [index.get(f"{year:04d}-Q{q}") for q in (1, 2, 3, 4)]
    vals = [v for v in vals if v is not None]
    if len(vals) < 4:
        return None
    return float(sum(vals))


@dataclass
class Ref:
    source: str
    dataset: str
    series: str
    value: float
    unit: str = ""


def metric_id(actor: str, country: str, metric: str, denominator: str, period: str) -> str:
    key = "|".join((actor, country, metric, denominator, period))
    return hashlib.sha256(key.encode()).hexdigest()


def emit(
    docs: list[dict[str, Any]],
    *,
    actor: str,
    country: str,
    metric: str,
    denominator: str,
    period: str,
    numerator: Ref,
    denominator_ref: Ref,
) -> None:
    if denominator_ref.value <= 0:
        return
    value = round(numerator.value / denominator_ref.value * 100.0, 4)
    if abs(value) > 10_000:  # unit mismatch guard
        return
    docs.append(
        {
            "_id": metric_id(actor, country, metric, denominator, period),
            "actor": actor,
            "country": country,
            "metric": metric,
            "denominator": denominator,
            "period": period,
            "period_type": "quarter" if qkey(period) else "year",
            "value": value,
            "unit": "percent",
            "method": "observed",
            "numerator": asdict(numerator),
            "denominator_ref": asdict(denominator_ref),
            "computed_at": datetime.now(UTC),
        }
    )


def emit_passthrough(
    docs: list[dict[str, Any]],
    *,
    actor: str,
    country: str,
    metric: str,
    denominator: str,
    period: str,
    value: float,
    ref: Ref,
) -> None:
    docs.append(
        {
            "_id": metric_id(actor, country, metric, denominator, period),
            "actor": actor,
            "country": country,
            "metric": metric,
            "denominator": denominator,
            "period": period,
            "period_type": "quarter" if qkey(period) else "year",
            "value": round(float(value), 4),
            "unit": "percent",
            "method": "observed",
            "numerator": asdict(ref),
            "denominator_ref": {"source": "published", "dataset": ref.dataset, "series": ref.series, "value": float(value), "unit": "percent (as published)"},
            "computed_at": datetime.now(UTC),
        }
    )


# ----------------------------------------------------------------- loaders ---
async def _load(repo: MongoRepository) -> dict[str, Any]:
    """Fetch every input family into in-memory indexes."""

    async def bis_stocks() -> dict:
        rows = await repo.find_many(
            "bis",
            {
                "dataset": "WS_TC",
                "dimensions.TC_LENDERS": "A",
                "dimensions.TC_ADJUST": "A",
                "dimensions.VALUATION": "M",
                "dimensions.TC_BORROWERS": {"$in": ["H", "N", "G"]},
                "dimensions.UNIT_TYPE": {"$in": ["XDC", "USD"]},
            },
            {"dimensions": 1, "period": 1, "value": 1, "dataset": 1},
        )
        levels: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
        for r in rows:
            d = r["dimensions"]
            cty, borr = d.get("BORROWERS_CTY", ""), d.get("TC_BORROWERS", "")
            if d.get("UNIT_MEASURE") != CURRENCY.get(cty):
                continue  # national-currency rows only
            levels[(cty, borr)][r["period"]] = float(r["value"])
        pct_rows = await repo.find_many(
            "bis",
            {
                "dataset": "WS_TC",
                "dimensions.TC_LENDERS": "A",
                "dimensions.TC_ADJUST": "A",
                "dimensions.VALUATION": "M",
                "dimensions.TC_BORROWERS": "G",
                "dimensions.UNIT_TYPE": "770",
            },
            {"dimensions": 1, "period": 1, "value": 1},
        )
        pct: dict[str, dict[str, float]] = defaultdict(dict)
        for r in pct_rows:
            pct[r["dimensions"].get("BORROWERS_CTY", "")][r["period"]] = float(r["value"])
        return {"levels": dict(levels), "pct_gdp": dict(pct)}

    async def bis_dsr() -> dict:
        rows = await repo.find_many(
            "bis",
            {"dataset": "WS_DSR"},
            {"dimensions": 1, "period": 1, "value": 1},
        )
        out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
        for r in rows:
            d = r["dimensions"]
            out[(d.get("BORROWERS_CTY", ""), d.get("DSR_BORROWERS", ""))][r["period"]] = float(r["value"])
        return dict(out)

    async def bis_dss() -> dict:
        rows = await repo.find_many(
            "bis",
            {
                "dataset": "WS_NA_SEC_DSS",
                "dimensions.COUNTERPART_AREA": "XW",
                "dimensions.COUNTERPART_SECTOR": "S1",
            },
            {"dimensions": 1, "period": 1, "value": 1},
        )
        best: dict[tuple[str, str, str, str], tuple[float, bool]] = {}
        for r in rows:
            d = r["dimensions"]
            key = (d.get("REF_AREA", ""), d.get("REF_SECTOR", ""), d.get("MATURITY", ""), r["period"])
            native = d.get("UNIT_MEASURE") == CURRENCY.get(key[0])
            value = float(r["value"])
            if key not in best or (native and not best[key][1]):
                best[key] = (value, native)
        out: dict[tuple[str, str], dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
        for (cty, sector, maturity, period), (value, _) in best.items():
            out[(cty, sector)][maturity][period] = value
        return {k: {m: dict(v) for m, v in secs.items()} for k, secs in out.items()}

    async def eurostat(dataset: str, series: set[str] | None = None) -> dict:
        query: dict[str, Any] = {"source": "eurostat", "dataset": dataset}
        if series:
            query["series"] = {"$in": sorted(series)}
        rows = await repo.find_many("eurostat", query, {"series": 1, "country": 1, "period": 1, "value": 1, "unit": 1})
        out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
        for r in rows:
            out[(r["series"], r["country"])][r["period"]] = float(r["value"])
        return dict(out)

    async def fred(series: tuple[str, ...]) -> dict:
        rows = await repo.find_many(
            "fred", {"series": {"$in": list(series)}}, {"series": 1, "period": 1, "value": 1}
        )
        out: dict[str, dict[str, float]] = defaultdict(dict)
        for r in rows:
            out[r["series"]][r["period"]] = float(r["value"])
        return dict(out)

    async def dbnomics(series: tuple[str, ...] | None = None, dataset: str | None = None) -> dict:
        query: dict[str, Any] = {"source": "dbnomics"}
        if series:
            query["series"] = {"$in": list(series)}
        if dataset:
            query["dataset"] = dataset
        rows = await repo.find_many(
            "dbnomics", query, {"series": 1, "country": 1, "period": 1, "value": 1, "dataset": 1}
        )
        out: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
        for r in rows:
            out[(r["dataset"], r["series"], r.get("country", ""))][r["period"]] = float(r["value"])
        return dict(out)

    async def imf(series: tuple[str, ...]) -> dict:
        rows = await repo.find_many(
            "imf", {"dataset": "WEO", "series": {"$in": list(series)}},
            {"series": 1, "country": 1, "period": 1, "value": 1},
        )
        out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
        for r in rows:
            out[(r["series"], r["country"])][r["period"]] = float(r["value"])
        return dict(out)

    z1_ons = (
        "FA156130005.Q", "FA106130001.Q", "FA366130005.Q",
        "HABN.Q", "HAAJ.Q", "HACY.Q", "EABG.Q", "I69W.Q", "I69X.Q", "CGBZ.Q",
        "Q.US.NGDP_SA_XDC", "Q.GB.NGDP_SA_XDC", "Q.JP.NGDP_SA_XDC", "Q.DE.NGDP_SA_XDC",
    )
    results = await asyncio.gather(
        bis_stocks(),
        bis_dsr(),
        bis_dss(),
        eurostat("nasq_10_nf_tr"),
        eurostat("nasa_10_nf_tr"),
        eurostat("gov_10a_main"),
        eurostat("namq_10_gdp"),
        fred(("DPI", "B069RC1Q027SBEA", "A091RC1Q027SBEA", "Y705RC1Q027SBEA", "A455RC1Q027SBEA")),
        dbnomics(series=z1_ons),
        dbnomics(dataset={"$in": ["OECD/DSD_NASEC10@DF_TABLE12", "OECD/DSD_NASEC10@DF_TABLE12_EXP"]}),
        imf(("GGXWDG", "NGDP", "GGXWDG_NGDP")),
    )
    return {
        "bis_tc": results[0],
        "bis_dsr": results[1],
        "bis_dss": results[2],
        "nasq": results[3],
        "nasa": results[4],
        "gov_main": results[5],
        "namq": results[6],
        "fred": results[7],
        "dbn": results[8],
        "t12": results[9],
        "weo": results[10],
    }


# ---------------------------------------------------------------- builders ---
def _t12_index(t12: dict, side: str, transaction: str) -> dict[str, dict[str, float]]:
    """(dataset, series, country-iso3) index -> {iso2: {year: value billions}}.

    `side` filters the account side: "D" = expenditure (interest), "C" = revenue
    (total revenue). Table 12 also carries a colliding C.D41 entry for some
    countries (capital-side), so the side must be pinned.
    """
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for (_, series, iso3), periods in t12.items():
        code = series.split(".")
        if len(code) < 6 or code[4] != side or code[5] != transaction:
            continue
        iso2 = ISO3_TO_2.get(iso3)
        if not iso2:
            continue
        for year, value in periods.items():
            if len(year) == 4 and year.isdigit():
                out[iso2][year] = value / 1_000.0
    return dict(out)


def build_private(data: dict[str, Any]) -> list[dict[str, Any]]:
    """M1/M3 quarterly for households & NFC (EU + US + GB), M2 via BIS DSR."""
    docs: list[dict[str, Any]] = []
    nasq, tc, dsr = data["nasq"], data["bis_tc"]["levels"], data["bis_dsr"]
    fred, dbn = data["fred"], data["dbn"]

    def dbn_series(code: str) -> dict[str, float]:
        for (_dataset, series, _), periods in dbn.items():
            if series == code:
                return periods
        return {}

    spec = {
        HH: {
            "bis_borrower": "H",
            "eu_interest": "D41_S14_S15",
            "eu_income": "B6G_S14_S15",
            "income_den": "disposable_income",
        },
        NFC: {
            "bis_borrower": "N",
            "eu_interest": "D41_S11",
            "eu_income": "B2A3G_S11",
            "income_den": "gross_operating_surplus",
        },
        FC: {
            "bis_borrower": "",
            "eu_interest": "D41_S12",
            "eu_income": "B2A3G_S12",
            "income_den": "gross_operating_surplus",
        },
    }

    # --- Eurostat geos (quarterly flows in millions -> TTM -> billions) ---
    for actor, cfg in spec.items():
        for geo in EU_GEOS + AGG_GEOS:
            interest = nasq.get((cfg["eu_interest"], geo), {})
            income = nasq.get((cfg["eu_income"], geo), {})
            if not interest or not income:
                continue
            periods = sorted(set(interest) & set(income), key=lambda p: qkey(p) or (0, 0))
            for period in periods:
                int_ttm = ttm(interest, period)
                inc_ttm = ttm(income, period)
                if int_ttm is None or inc_ttm is None or inc_ttm <= 0:
                    continue
                emit(
                    docs,
                    actor=actor,
                    country=geo,
                    metric=M_INTEREST,
                    denominator=cfg["income_den"],
                    period=period,
                    numerator=Ref("eurostat", "nasq_10_nf_tr", cfg["eu_interest"], round(int_ttm / 1_000.0, 3), "TTM, national currency billions"),
                    denominator_ref=Ref("eurostat", "nasq_10_nf_tr", cfg["eu_income"], round(inc_ttm / 1_000.0, 3), "TTM, national currency billions"),
                )
                stock_idx = tc.get((geo, cfg["bis_borrower"]), {}) if cfg["bis_borrower"] else {}
                stock = stock_idx.get(period)
                if stock is not None:
                    emit(
                        docs,
                        actor=actor,
                        country=geo,
                        metric=M_DEBT,
                        denominator=cfg["income_den"],
                        period=period,
                        numerator=Ref("bis", "WS_TC", cfg["bis_borrower"], float(stock), "stock, national currency billions"),
                        denominator_ref=Ref("eurostat", "nasq_10_nf_tr", cfg["eu_income"], round(inc_ttm / 1_000.0, 3), "TTM, national currency billions"),
                    )

    # --- United States (SAAR billions as-is) ---
    def to_quarters(index: dict[str, float]) -> dict[str, float]:
        """DBnomics .Q series keys are dates ('2026-06-30') — canonicalise."""
        out: dict[str, float] = {}
        for period, value in index.items():
            if len(period) == 10:
                q = f"{period[:4]}-Q{(int(period[5:7]) - 1) // 3 + 1}"
                out[q] = value  # same-quarter upserts collapse to the last value
            else:
                out[period] = value
        return out

    us_pairs = [
        (HH, "B069RC1Q027SBEA", "DPI", "disposable_income", "H"),
        (NFC, "FA106130001.Q", "A455RC1Q027SBEA", "gross_value_added", "N"),
    ]
    for actor, int_code, inc_code, den, borrower in us_pairs:
        interest = fred.get(int_code) or to_quarters(dbn_series(int_code))
        income = fred.get(inc_code)
        stock = tc.get(("US", borrower), {})
        if not interest or not income:
            continue
        for period in sorted(set(interest) & set(income)):
            inc = income[period]
            int_v = interest[period] / (1_000.0 if int_code.startswith("FA") else 1.0)
            emit(
                docs,
                actor=actor,
                country="US",
                metric=M_INTEREST,
                denominator=den,
                period=period,
                numerator=Ref("fred-or-z1", "", int_code, round(int_v, 3), "SAAR billions"),
                denominator_ref=Ref("fred", "FRED", inc_code, float(inc), "SAAR billions"),
            )
            st = stock.get(period)
            if st is not None:
                emit(
                    docs,
                    actor=actor,
                    country="US",
                    metric=M_DEBT,
                    denominator=den,
                    period=period,
                    numerator=Ref("bis", "WS_TC", borrower, float(st), "stock, national currency billions"),
                    denominator_ref=Ref("fred", "FRED", inc_code, float(inc), "SAAR billions"),
                )

    # --- United Kingdom (quarterly flows in GBP millions -> TTM -> billions) ---
    gb_pairs = [
        (HH, "HACY.Q", ("HABN.Q", "HAAJ.Q"), "disposable_income", "H"),
        (NFC, "EABG.Q", ("CGBZ.Q",), "gross_operating_surplus", "N"),
    ]
    for actor, int_code, inc_codes, den, borrower in gb_pairs:
        interest = dbn_series(int_code)
        incomes = [dbn_series(c) for c in inc_codes]
        stock = tc.get(("GB", borrower), {})
        if not interest or not all(incomes):
            continue
        for period in sorted(set(interest) & set(incomes[0])):
            int_ttm = ttm(interest, period)
            inc_ttm = ttm(incomes[0], period)
            if incomes[1:]:
                second = ttm(incomes[1], period)
                if second is not None:
                    inc_ttm = (inc_ttm or 0) + second
            if int_ttm is None or not inc_ttm or inc_ttm <= 0:
                continue
            emit(
                docs,
                actor=actor,
                country="GB",
                metric=M_INTEREST,
                denominator=den,
                period=period,
                numerator=Ref("ons", "ONS/UKEA", int_code, round(int_ttm / 1_000.0, 3), "TTM, GBP billions"),
                denominator_ref=Ref("ons", "ONS/UKEA", "+".join(inc_codes), round(inc_ttm / 1_000.0, 3), "TTM, GBP billions"),
            )
            st = stock.get(period)
            if st is not None:
                emit(
                    docs,
                    actor=actor,
                    country="GB",
                    metric=M_DEBT,
                    denominator=den,
                    period=period,
                    numerator=Ref("bis", "WS_TC", borrower, float(st), "stock, GBP billions"),
                    denominator_ref=Ref("ons", "ONS/UKEA", "+".join(inc_codes), round(inc_ttm / 1_000.0, 3), "TTM, GBP billions"),
                )

    # --- Switzerland (annual sector accounts) ---
    nasa = data["nasa"]
    for actor, cfg in spec.items():
        interest = nasa.get((cfg["eu_interest"], "CH"), {})
        income = nasa.get((cfg["eu_income"], "CH"), {})
        for year in sorted(set(interest) & set(income)):
            if income[year] > 0:
                emit(
                    docs,
                    actor=actor,
                    country="CH",
                    metric=M_INTEREST,
                    denominator=cfg["income_den"],
                    period=year,
                    numerator=Ref("eurostat", "nasa_10_nf_tr", cfg["eu_interest"], round(interest[year] / 1_000.0, 3), "CHF millions"),
                    denominator_ref=Ref("eurostat", "nasa_10_nf_tr", cfg["eu_income"], round(income[year] / 1_000.0, 3), "CHF millions"),
                )
                stock_idx = tc.get(("CH", cfg["bis_borrower"]), {}) if cfg["bis_borrower"] else {}
                q4 = stock_idx.get(f"{year}-Q4")
                if q4 is not None:
                    emit(
                        docs,
                        actor=actor,
                        country="CH",
                        metric=M_DEBT,
                        denominator=cfg["income_den"],
                        period=year,
                        numerator=Ref("bis", "WS_TC", cfg["bis_borrower"], float(q4), "stock, CHF billions"),
                        denominator_ref=Ref("eurostat", "nasa_10_nf_tr", cfg["eu_income"], round(income[year] / 1_000.0, 3), "CHF millions"),
                    )

    # --- M2: BIS DSR pass-through (households & NFC) ---
    for (cty, borrower), periods in dsr.items():
        actor = {"H": HH, "N": NFC}.get(borrower)
        if not actor:
            continue
        den = "disposable_income" if borrower == "H" else "gross_operating_surplus"
        for period, value in periods.items():
            emit_passthrough(
                docs,
                actor=actor,
                country=cty,
                metric=M_SERVICE,
                denominator=den,
                period=period,
                value=value,
                ref=Ref("bis", "WS_DSR", borrower, float(value), "percent (interest + amortisation, as published)"),
            )
    return docs


def build_government(data: dict[str, Any]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    nasq, namq, gov_main = data["nasq"], data["namq"], data["gov_main"]
    tc, pct_gdp, dss = data["bis_tc"]["levels"], data["bis_tc"]["pct_gdp"], data["bis_dss"]
    dbn, weo = data["dbn"], data["weo"]
    t12_interest = _t12_index(data["t12"], "D", "D41")
    t12_revenue = _t12_index(data["t12"], "C", "OTR")

    def dbn_series(code: str) -> dict[str, float]:
        for (_dataset, series, _), periods in dbn.items():
            if series == code:
                return periods
        return {}

    # ---- quarterly interest index per country (billions TTM) ----
    interest_q: dict[str, dict[str, float]] = defaultdict(dict)
    interest_q_src: dict[str, str] = {}
    for geo in EU_GEOS + AGG_GEOS:
        idx = nasq.get(("D41_S13", geo), {})
        for period in idx:
            v = ttm(idx, period)
            if v is not None:
                interest_q[geo][period] = v / 1_000.0
        if interest_q[geo]:
            interest_q_src[geo] = "eurostat:nasq_10_nf_tr:D41_S13"
    for period, v in dbn_series("FA366130005.Q").items():
        q = f"{period[:4]}-Q{(int(period[5:7]) - 1) // 3 + 1}"
        interest_q["US"][q] = v / 1_000.0
    interest_q_src["US"] = "dbnomics:FED/Z1:FA366130005.Q"
    for period in dbn_series("I69W.Q"):
        a, b = dbn_series("I69W.Q"), dbn_series("I69X.Q")
        if period in b:
            va, vb = ttm(a, period), ttm(b, period)
            if va is not None and vb is not None:
                interest_q["GB"][period] = (va + vb) / 1_000.0
    interest_q_src["GB"] = "ons:UKEA:I69W.Q+I69X.Q"

    # ---- quarterly GDP index per country (billions TTM) ----
    gdp_q: dict[str, dict[str, float]] = defaultdict(dict)
    for geo in EU_GEOS + AGG_GEOS:
        idx = namq.get(("B1GQ", geo), {})
        for period in idx:
            v = ttm(idx, period)
            if v is not None:
                gdp_q[geo][period] = v / 1_000.0
    for cty in ("US", "GB", "JP", "DE"):
        idx = dbn_series(f"Q.{cty}.NGDP_SA_XDC")
        for period in idx:
            v = ttm(idx, period)
            if v is not None:
                gdp_q[cty][period] = v / 1_000.0

    # ---- annual interest / revenue / GDP / debt (billions) ----
    # WEO serves raw national-currency units (DE 2025 GDP = 4.53e12 = €4.53tn)
    # despite the collector's unit label; scale to billions.
    def _scale_billions(idx: dict[str, float]) -> dict[str, float]:
        return {p: v / 1e9 for p, v in idx.items()}

    weo_gdp = {ISO3_TO_2.get(c, c): _scale_billions(p) for (ind, c), p in weo.items() if ind == "NGDP"}
    weo_debt = {ISO3_TO_2.get(c, c): _scale_billions(p) for (ind, c), p in weo.items() if ind == "GGXWDG"}
    weo_debt_pct = {ISO3_TO_2.get(c, c): p for (ind, c), p in weo.items() if ind == "GGXWDG_NGDP"}

    def gov_revenue_annual(geo: str) -> dict[str, float]:
        idx = gov_main.get(("TR_MIO_NAC", geo), {})
        out = {y: v / 1_000.0 for y, v in idx.items() if y.isdigit()}
        if not out:
            out = t12_revenue.get(geo, {})
        return out

    def gov_interest_annual(geo: str) -> dict[str, float]:
        return t12_interest.get(geo, {})

    def debt_q(geo: str) -> dict[str, float]:
        return tc.get((geo, "G"), {})

    # ---- 1) quarterly: interest/GDP, (interest+maturing)/GDP, debt/GDP ----
    for geo, interest in interest_q.items():
        gdps = gdp_q.get(geo, {})
        stocks = debt_q(geo)
        mat = dss.get((geo, "S13"), {})
        for period, int_v in interest.items():
            gdp_v = gdps.get(period)
            if gdp_v:
                emit(
                    docs,
                    actor=GOV,
                    country=geo,
                    metric=M_INTEREST,
                    denominator="gdp",
                    period=period,
                    numerator=Ref(*interest_q_src[geo].split(":"), round(int_v, 3), "TTM billions"),
                    denominator_ref=Ref("various", "GDP", "B1GQ/NGDP", round(gdp_v, 3), "TTM billions"),
                )
                # Maturing-principal proxy: securities with original maturity
                # <=1y (S) plus original >1y now due within 1y (LS). The US
                # publishes no LS split — S alone understates; documented.
                s_v = mat.get("S", {}).get(period)
                ls_v = mat.get("LS", {}).get(period)
                if s_v is not None or ls_v is not None:
                    maturing = (s_v or 0.0) + (ls_v or 0.0)
                    emit(
                        docs,
                        actor=GOV,
                        country=geo,
                        metric=M_SERVICE,
                        denominator="gdp",
                        period=period,
                        numerator=Ref("bis+various", "WS_NA_SEC_DSS+interest", "S+LS+D41", round(int_v + maturing, 3), "TTM interest + securities <=1y due, billions"),
                        denominator_ref=Ref("various", "GDP", "B1GQ/NGDP", round(gdp_v, 3), "TTM billions"),
                    )
            st = stocks.get(period)
            if st is not None and gdp_v:
                emit(
                    docs,
                    actor=GOV,
                    country=geo,
                    metric=M_DEBT,
                    denominator="gdp",
                    period=period,
                    numerator=Ref("bis", "WS_TC", "G", float(st), "stock, national currency billions"),
                    denominator_ref=Ref("various", "GDP", "B1GQ/NGDP", round(gdp_v, 3), "TTM billions"),
                )

    # BIS-published gov debt %GDP where no quarterly GDP join exists
    for geo, periods in pct_gdp.items():
        if geo in gdp_q:
            continue
        for period, value in periods.items():
            emit_passthrough(
                docs,
                actor=GOV,
                country=geo,
                metric=M_DEBT,
                denominator="gdp",
                period=period,
                value=value,
                ref=Ref("bis", "WS_TC", "G:770", float(value), "percent of GDP (as published)"),
            )

    # ---- 2) annual rows: OECD T12 interest + revenue + WEO GDP/debt ----
    all_geos = set(t12_interest) | set(t12_revenue) | set(weo_gdp)
    for geo in sorted(all_geos):
        years_int = t12_interest.get(geo, {})
        years_rev = gov_revenue_annual(geo)
        gdp_a = weo_gdp.get(geo, {})
        debt_a = weo_debt.get(geo, {})
        debt_pct_a = weo_debt_pct.get(geo, {})
        mat = dss.get((geo, "S13"), {})
        for year in sorted(set(years_int) & set(gdp_a)):
            emit(
                docs,
                actor=GOV,
                country=geo,
                metric=M_INTEREST,
                denominator="gdp",
                period=year,
                numerator=Ref("oecd", "T12_EXP", "D41", round(years_int[year], 3), "national currency billions"),
                denominator_ref=Ref("imf", "WEO", "NGDP", round(gdp_a[year], 3), "national currency billions"),
            )
            # Annual rollover-risk proxy: T12 interest + securities maturing
            # within 1 year (S + LS at year-end).
            s_v = mat.get("S", {}).get(f"{year}-Q4")
            ls_v = mat.get("LS", {}).get(f"{year}-Q4")
            if s_v is not None or ls_v is not None:
                maturing = (s_v or 0.0) + (ls_v or 0.0)
                emit(
                    docs,
                    actor=GOV,
                    country=geo,
                    metric=M_SERVICE,
                    denominator="gdp",
                    period=year,
                    numerator=Ref("oecd+bis", "T12_EXP+WS_NA_SEC_DSS", "D41+S+LS", round(years_int[year] + maturing, 3), "interest + securities <=1y due, billions"),
                    denominator_ref=Ref("imf", "WEO", "NGDP", round(gdp_a[year], 3), "national currency billions"),
                )
        for year in sorted(set(years_int) & set(years_rev)):
            if years_rev[year] > 0:
                emit(
                    docs,
                    actor=GOV,
                    country=geo,
                    metric=M_INTEREST,
                    denominator="government_revenue",
                    period=year,
                    numerator=Ref("oecd", "T12_EXP", "D41", round(years_int[year], 3), "national currency billions"),
                    denominator_ref=Ref("oecd/eurostat", "T12/gov_10a_main", "OTR/TR", round(years_rev[year], 3), "national currency billions"),
                )
        for year in sorted(set(debt_a) & set(years_rev)):
            if years_rev[year] > 0:
                emit(
                    docs,
                    actor=GOV,
                    country=geo,
                    metric=M_DEBT,
                    denominator="government_revenue",
                    period=year,
                    numerator=Ref("imf", "WEO", "GGXWDG", round(debt_a[year], 3), "national currency billions"),
                    denominator_ref=Ref("oecd/eurostat", "T12/gov_10a_main", "OTR/TR", round(years_rev[year], 3), "national currency billions"),
                )
        for year, value in debt_pct_a.items():
            emit_passthrough(
                docs,
                actor=GOV,
                country=geo,
                metric=M_DEBT,
                denominator="gdp",
                period=year,
                value=value,
                ref=Ref("imf", "WEO", "GGXWDG_NGDP", float(value), "percent of GDP (as published)"),
            )
    return docs


# ------------------------------------------------------------------ entry ----
async def compute_and_store(repo: MongoRepository) -> dict[str, int]:
    data = await _load(repo)
    docs = build_private(data) + build_government(data)
    # de-duplicate identical _ids produced by overlapping paths
    unique = {d["_id"]: d for d in docs}
    n = await repo.upsert_docs("metrics", list(unique.values()))
    logger.info("metrics: %d computed (%d stored)", len(unique), n)
    return {"computed": len(unique), "stored": n}


def coverage_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarise stored metric docs into (actor, metric, denominator) coverage."""
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in rows:
        key = (r["actor"], r["metric"], r["denominator"])
        cur = best.get(key)
        if cur is None:
            best[key] = {"latest": r["period"], "countries": {r["country"]}}
        else:
            cur["countries"].add(r["country"])
            if r["period"] > cur["latest"]:
                cur["latest"] = r["period"]
    out = []
    for (actor, metric, denominator), info in sorted(best.items()):
        out.append(
            {
                "actor": actor,
                "metric": metric,
                "denominator": denominator,
                "countries": len(info["countries"]),
                "latest": info.get("latest", ""),
            }
        )
    return out


def to_tidy_csv(docs: list[dict[str, Any]]) -> str:
    import csv
    import io

    fields = [
        "actor", "country", "metric", "denominator", "period", "period_type",
        "value", "unit", "method", "numerator_source", "numerator_series",
        "denominator_source", "denominator_series",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for d in sorted(docs, key=lambda x: (x["actor"], x["country"], x["metric"], x["denominator"], x["period"])):
        writer.writerow(
            {
                **{f: d.get(f, "") for f in fields},
                "numerator_source": d.get("numerator", {}).get("source", ""),
                "numerator_series": d.get("numerator", {}).get("series", ""),
                "denominator_source": d.get("denominator_ref", {}).get("source", ""),
                "denominator_series": d.get("denominator_ref", {}).get("series", ""),
                "value": json.dumps(d.get("value")),
            }
        )
    return buf.getvalue()
