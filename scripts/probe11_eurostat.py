"""Dossier-11 probe: Eurostat sector accounts (interest + income) and gov revenue.

Targets (dossier 11, cards 1-3):
  1. nasq_10_nf_tr  — quarterly non-financial transactions by sector:
       na_item D41 (interest payable) x sectors S11/S12/S13/S14_S15
       income aggregates B6G (HH disposable), B2G_B3G (operating surplus), B1G
  2. nasa_10_nf_tr  — annual fallback for annual-only reporters
  3. gov_10a_main   — general government total revenue (TR) for the revenue
       denominator variant
  4. nasq_10_f_bs   — retry of the open item (OVERVIEW §5.1): sector debt
       stocks F3/F4 server-side filter

Run: uv run python scripts/probe11_eurostat.py
"""

import time

import httpx

API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
UA = {"User-Agent": "debt-monitor-probe/0.1 (research)"}


def probe(client: httpx.Client, dataset: str, params: dict, label: str) -> None:
    t0 = time.time()
    try:
        r = client.get(f"{API}/{dataset}", params=params, headers=UA, timeout=120)
        dt = time.time() - t0
        if r.status_code != 200:
            print(f"[{label}] {dataset} HTTP {r.status_code} ({dt:.1f}s): {r.text[:220]}")
            return
        js = r.json()
        ids, sizes = js.get("id", []), js.get("size", [])
        n_values = len(js.get("value", {}))
        dims_desc = ", ".join(f"{i}={s}" for i, s in zip(ids, sizes, strict=True))
        print(f"[{label}] {dataset} 200 ({dt:.1f}s, {len(r.content)//1024} KB) dims[{dims_desc}] values={n_values}")
        # show category lists of the non-filtered dims (truncated)
        for dim in ids:
            cats = list(js["dimension"][dim]["category"]["index"].keys())
            if len(cats) > 40:
                print(f"    {dim}: {len(cats)} codes (first 12): {cats[:12]}")
            else:
                print(f"    {dim}: {cats}")
        # sample the latest observations
        times = sorted(js["dimension"]["time"]["category"]["index"], key=str)
        inv_time = {pos: code for code, pos in js["dimension"]["time"]["category"]["index"].items()}
        flat_values = js.get("value", {})
        if flat_values and times:
            last = inv_time[max(pos for pos in inv_time)]
            # brute force: walk the full grid like parse_jsonstat
            from itertools import product

            codes_per_dim = []
            for dim in ids:
                idx = js["dimension"][dim]["category"]["index"]
                inv = {pos: code for code, pos in idx.items()}
                codes_per_dim.append([inv[i] for i in range(sizes[ids.index(dim)])])
            for flat_pos, combo in enumerate(product(*codes_per_dim)):
                if combo[ids.index("time")] != last:
                    continue
                v = flat_values.get(str(flat_pos))
                if v is not None:
                    print(f"    latest[{last}]: {'/'.join(combo)} = {v}")
    except Exception as exc:  # noqa: BLE001
        print(f"[{label}] {dataset} ERROR {type(exc).__name__}: {exc}")
    time.sleep(0.5)


def main() -> None:
    with httpx.Client() as client:
        base = {"format": "JSON", "lang": "EN"}

        # --- 1a. nasq_10_nf_tr: HH interest payable, EA20, try units ---
        for unit in ("CP_MNACSA", "CP_MNAC"):
            probe(
                client,
                "nasq_10_nf_tr",
                base
                | {
                    "freq": "Q",
                    "unit": unit,
                    "na_item": "D41",
                    "sector": "S14_S15",
                    "geo": "EA20",
                    "sinceTimePeriod": "2024-Q1",
                },
                f"D41 HH EA20 unit={unit}",
            )

        # --- 1b. same but government sector ---
        probe(
            client,
            "nasq_10_nf_tr",
            base
            | {
                "freq": "Q",
                "unit": "CP_MNACSA",
                "na_item": "D41",
                "sector": "S13",
                "geo": "EA20",
                "sinceTimePeriod": "2024-Q1",
            },
            "D41 gov EA20",
        )

        # --- 1c. HH disposable income B6G ---
        probe(
            client,
            "nasq_10_nf_tr",
            base
            | {
                "freq": "Q",
                "unit": "CP_MNACSA",
                "na_item": "B6G",
                "sector": "S14_S15",
                "geo": "EA20",
                "sinceTimePeriod": "2024-Q1",
            },
            "B6G HH EA20",
        )

        # --- 1d. NFC operating surplus B2G_B3G ---
        probe(
            client,
            "nasq_10_nf_tr",
            base
            | {
                "freq": "Q",
                "unit": "CP_MNACSA",
                "na_item": "B2G_B3G",
                "sector": "S11",
                "geo": "EA20",
                "sinceTimePeriod": "2024-Q1",
            },
            "B2G_B3G NFC EA20",
        )

        # --- 1e. one small EU member to check country-level availability ---
        probe(
            client,
            "nasq_10_nf_tr",
            base
            | {
                "freq": "Q",
                "unit": "CP_MNACSA",
                "na_item": "D41",
                "sector": "S14_S15",
                "geo": "PT",
                "sinceTimePeriod": "2024-Q1",
            },
            "D41 HH PT",
        )

        # --- 2. nasa_10_nf_tr annual fallback (NO/CH are annual-only reporters) ---
        for geo in ("NO", "CH", "JP", "US", "GB"):
            probe(
                client,
                "nasa_10_nf_tr",
                base
                | {
                    "freq": "A",
                    "unit": "CP_MNACSA" if geo in ("NO", "CH") else "CP_MIO_EUR",
                    "na_item": "D41",
                    "sector": "S14_S15",
                    "geo": geo,
                    "sinceTimePeriod": "2023",
                },
                f"annual D41 HH {geo}",
            )

        # --- 3. gov_10a_main total revenue: try candidate na_item codes ---
        for item in ("TR", "TE", "T1"):
            probe(
                client,
                "gov_10a_main",
                base
                | {
                    "freq": "Q",
                    "unit": "MIO_NAC",
                    "na_item": item,
                    "sector": "S13",
                    "geo": "EA20",
                    "sinceTimePeriod": "2024-Q1",
                },
                f"gov_10a_main item={item}",
            )

        # --- 4. nasq_10_f_bs retry: exact-dimension filter ---
        probe(
            client,
            "nasq_10_f_bs",
            base
            | {
                "freq": "Q",
                "unit": "MIO_NAC" if False else "CP_MNACSA",
                "na_item": "F4",
                "sector": "S14_S15",
                "geo": "EA20",
                "sinceTimePeriod": "2024-Q1",
            },
            "f_bs F4 HH EA20 retry",
        )


if __name__ == "__main__":
    main()
