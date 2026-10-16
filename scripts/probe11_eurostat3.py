"""Dossier-11 probe round 3: full sector x na_item verification on nasq_10_nf_tr,
quarterly gov revenue hunt, EDP quarterly check, nasa_10_nf_tr annual units.

Run: uv run python scripts/probe11_eurostat3.py
"""

import time
from itertools import product

import httpx

API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
UA = {"User-Agent": "debt-monitor-probe/0.1 (research)"}


def probe(client: httpx.Client, dataset: str, params: dict, label: str, show: int = 0) -> None:
    try:
        r = client.get(f"{API}/{dataset}", params=params, headers=UA, timeout=180)
        if r.status_code != 200:
            print(f"[{label}] {dataset} HTTP {r.status_code}: {r.text[:200]}")
            return
        js = r.json()
        ids, sizes = js.get("id", []), js.get("size", [])
        n_values = len(js.get("value", {}))
        print(f"[{label}] {dataset} 200 values={n_values}")
        if not n_values:
            for dim in ids:
                idx = js["dimension"][dim]["category"]["index"]
                cats = [c for c, _ in sorted(idx.items(), key=lambda kv: kv[1])]
                print(f"    {dim}: {cats if len(cats) < 40 else f'{len(cats)} codes'}")
            return
        codes_per_dim = []
        for dim in ids:
            idx = js["dimension"][dim]["category"]["index"]
            inv = {pos: code for code, pos in idx.items()}
            codes_per_dim.append([inv[i] for i in range(sizes[ids.index(dim)])])
        rows = []
        for flat_pos, combo in enumerate(product(*codes_per_dim)):
            v = js["value"].get(str(flat_pos))
            if v is not None:
                rows.append(("/".join(c for c in combo if not c.isdigit() or len(c) > 4), v))
        # print the newest periods first
        for combo, v in sorted(rows, key=lambda rv: rv[0])[-show:] if show else []:
            print(f"    {combo} = {v}")
    except Exception as exc:  # noqa: BLE001
        print(f"[{label}] {dataset} ERROR {type(exc).__name__}: {exc}")
    finally:
        time.sleep(0.5)


def main() -> None:
    with httpx.Client() as client:
        base = {"format": "JSON", "lang": "EN", "sinceTimePeriod": "2025-Q4"}

        # Multi-value filter support + all 4 sectors' D41 payable in one query
        probe(
            client,
            "nasq_10_nf_tr",
            base | {"freq": "Q", "unit": "CP_MEUR", "na_item": "D41", "direct": "PAID", "s_adj": "NSA", "geo": "DE"},
            "D41 all sectors DE",
            show=8,
        )

        # Income aggregates: HH B6G, NFC B2A3G, FC B2A3G, gov B2A3G? (multi na_item + multi sector)
        probe(
            client,
            "nasq_10_nf_tr",
            base
            | {
                "freq": "Q",
                "unit": "CP_MEUR",
                "na_item": ["B6G", "B2A3G", "B1G"],
                "sector": ["S14_S15", "S11", "S12"],
                "direct": "PAID",
                "s_adj": "NSA",
                "geo": "DE",
            },
            "income aggregates DE",
            show=12,
        )

        # Quarterly gov revenue hunt: candidate datasets
        for ds, extra in (
            ("gov_10q_ggna", {"geo": "DE", "sinceTimePeriod": "2025-Q3"}),
            ("gov_10q_edpt1", {"geo": "DE", "sinceTimePeriod": "2025-Q3"}),
            ("gov_10dd_edpt1", {"freq": "Q", "geo": "DE", "na_item": "GD", "sector": "S13", "unit": "MIO_EUR"}),
        ):
            probe(client, ds, {"format": "JSON", "lang": "EN"} | extra, f"{ds}")

        # EDP quarterly debt + interest: does gov_10dd_edpt1 serve freq=Q?
        probe(
            client,
            "gov_10dd_edpt1",
            {"format": "JSON", "lang": "EN", "freq": "Q", "geo": "DE", "na_item": "GD", "sector": "S13", "unit": "PC_GDP", "sinceTimePeriod": "2025-Q1"},
            "EDP GD quarterly?",
            show=6,
        )

        # nasa_10_nf_tr annual: units + non-EU geo availability
        probe(
            client,
            "nasa_10_nf_tr",
            {"format": "JSON", "lang": "EN", "freq": "A", "na_item": "D41", "sector": "S14_S15", "direct": "PAID", "geo": "CH", "sinceTimePeriod": "2023"},
            "nasa D41 HH CH",
            show=6,
        )
        probe(
            client,
            "nasa_10_nf_tr",
            {"format": "JSON", "lang": "EN", "freq": "A", "na_item": "D41", "sector": "S14_S15", "direct": "PAID", "geo": "JP", "sinceTimePeriod": "2023"},
            "nasa D41 HH JP",
        )
        probe(
            client,
            "nasa_10_nf_tr",
            {"format": "JSON", "lang": "EN", "freq": "A", "na_item": "D41", "sector": "S14_S15", "direct": "PAID", "geo": "US", "sinceTimePeriod": "2023"},
            "nasa D41 HH US",
        )

        # Geo universe of the annual dataset (leave geo unfiltered)
        probe(
            client,
            "nasa_10_nf_tr",
            {"format": "JSON", "lang": "EN", "freq": "A", "na_item": "D41", "sector": "S14_S15", "direct": "PAID", "geo": "NO", "sinceTimePeriod": "2024"},
            "nasa D41 HH NO",
            show=4,
        )


if __name__ == "__main__":
    main()
