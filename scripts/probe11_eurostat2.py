"""Dossier-11 probe round 2: enumerate valid dimension values for Eurostat
sector-accounts datasets (round 1: filters zero out silently -> values=0).

Run: uv run python scripts/probe11_eurostat2.py
"""

import time
from itertools import product

import httpx

API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
UA = {"User-Agent": "debt-monitor-probe/0.1 (research)"}


def probe(client: httpx.Client, dataset: str, params: dict, label: str, show_values: bool = False) -> dict | None:
    try:
        r = client.get(f"{API}/{dataset}", params=params, headers=UA, timeout=180)
        if r.status_code != 200:
            print(f"[{label}] {dataset} HTTP {r.status_code}: {r.text[:200]}")
            return None
        js = r.json()
        ids, sizes = js.get("id", []), js.get("size", [])
        n_values = len(js.get("value", {}))
        print(f"[{label}] {dataset} 200 ({len(r.content)//1024} KB) values={n_values}")
        for dim in ids:
            idx = js["dimension"][dim]["category"]["index"]
            cats = [c for c, _ in sorted(idx.items(), key=lambda kv: kv[1])]
            if len(cats) > 60:
                print(f"    {dim}: {len(cats)} codes: {cats[:60]} ...")
            else:
                print(f"    {dim}: {cats}")
        if show_values and n_values:
            codes_per_dim = []
            for dim in ids:
                idx = js["dimension"][dim]["category"]["index"]
                inv = {pos: code for code, pos in idx.items()}
                codes_per_dim.append([inv[i] for i in range(sizes[ids.index(dim)])])
            shown = 0
            for flat_pos, combo in enumerate(product(*codes_per_dim)):
                v = js["value"].get(str(flat_pos))
                if v is not None:
                    print(f"    obs: {' / '.join(combo)} = {v}")
                    shown += 1
                    if shown >= 8:
                        break
        return js
    except Exception as exc:  # noqa: BLE001
        print(f"[{label}] {dataset} ERROR {type(exc).__name__}: {exc}")
        return None
    finally:
        time.sleep(0.5)


def main() -> None:
    with httpx.Client() as client:
        base = {"format": "JSON", "lang": "EN", "sinceTimePeriod": "2025-Q3"}

        # Enumerate geo + unit + s_adj for nasq_10_nf_tr, leaving them unfiltered
        probe(
            client,
            "nasq_10_nf_tr",
            base | {"freq": "Q", "na_item": "D41", "sector": "S14_S15", "direct": "PAID"},
            "nasq nf_tr dims (D41 HH PAID)",
            show_values=True,
        )

        # Enumerate valid na_item codes (income aggregates) for S11
        probe(
            client,
            "nasq_10_nf_tr",
            base | {"freq": "Q", "sector": "S11", "direct": "PAID", "geo": "DE"},
            "nasq nf_tr na_item codes for S11 DE",
        )

        # Valid B6G variant check: does B6G exist, or B6G_TRR? probe HH S14_S15 na_items
        probe(
            client,
            "nasq_10_nf_tr",
            base | {"freq": "Q", "sector": "S14_S15", "direct": "PAID", "geo": "DE"},
            "nasq nf_tr na_item codes for S14_S15 DE",
        )

        # gov_10a_main: freq + unit + na_item universe (annual expected)
        probe(
            client,
            "gov_10a_main",
            {"format": "JSON", "lang": "EN", "sinceTimePeriod": "2024", "geo": "DE", "sector": "S13", "na_item": "TR"},
            "gov_10a_main dims",
            show_values=True,
        )

        # Quarterly gov accounts: candidate dataset codes
        for ds in ("gov_10q_ggfa", "gov_q_ggfa", "gov_10q_main"):
            probe(client, ds, {"format": "JSON", "lang": "EN", "sinceTimePeriod": "2025-Q3", "geo": "DE"}, f"{ds} exists?")

        # nasq_10_f_bs: enumerate unit + na_item with everything else pinned
        probe(
            client,
            "nasq_10_f_bs",
            base | {"freq": "Q", "sector": "S14_S15", "finpos": "LIAB", "geo": "DE"},
            "f_bs unit/na_item universe",
        )


if __name__ == "__main__":
    main()
