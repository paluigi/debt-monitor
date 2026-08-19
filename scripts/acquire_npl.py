"""Acquire NPL data: World Bank annual (all economies) + IMF FSI quarterly/annual NPL ratio.

Outputs:
  data/wb_npl_annual.csv    — country, iso3, year, npl_pct (FB.AST.NPER.ZS)
  data/imf_fsi_npl.csv      — freq, iso2/dbnomics-code, country, period, npl_pct (FSANL_PT)
  data/imf_fsi_npl_summary.csv — per country: best freq, latest period, latest value
Single-file fetch+parse (no shell pipes). Run: python3 scripts/acquire_npl.py
"""
import csv
import io
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
UA = {"User-Agent": "debt-monitor/0.1 (research)"}
S = requests.Session()
S.headers.update(UA)

# ---------------------------------------------------------------- World Bank
def fetch_wb_npl():
    url = "https://api.worldbank.org/v2/country/all/indicator/FB.AST.NPER.ZS"
    rows, page, total = [], 1, None
    while True:
        r = S.get(url, params={"format": "json", "per_page": 1500, "page": page}, timeout=60)
        r.raise_for_status()
        meta, recs = r.json()[0], r.json()[1]
        total = total or meta["total"]
        for rec in recs:
            if rec["value"] is None:
                continue
            rows.append({
                "country": rec["country"]["value"],
                "iso3": rec["countryiso3code"],
                "year": rec["date"],
                "npl_pct": rec["value"],
            })
        if page * meta["per_page"] >= meta["total"]:
            break
        page += 1
        time.sleep(0.3)
    rows.sort(key=lambda x: (x["iso3"], x["year"]))
    out = DATA / "wb_npl_annual.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["country", "iso3", "year", "npl_pct"])
        w.writeheader()
        w.writerows(rows)
    n_cty = len({r["iso3"] for r in rows})
    yrs = sorted({r["year"] for r in rows})
    print(f"WB: {len(rows)} obs, {n_cty} economies, {yrs[0]}–{yrs[-1]} -> {out}")
    for c in ("USA", "CHN", "IND", "GBR", "JPN", "DEU"):
        last = [r for r in rows if r["iso3"] == c][-1]
        print(f"   {c}: {last['year']} = {last['npl_pct']:.3f}")
    return rows

# ---------------------------------------------------------------- IMF FSI via DBnomics
def fetch_fsi_npl():
    base = "https://api.db.nomics.world/v22"
    # 1) list all FSANL_PT series in IMF/FSI
    series, offset = [], 0
    while True:
        r = S.get(f"{base}/series/IMF/FSI",
                  params={"q": "FSANL_PT", "limit": 100, "offset": offset,
                          "observations": 0, "format": "json"}, timeout=60)
        r.raise_for_status()
        docs = r.json()["series"]["docs"]
        series.extend(docs)
        if len(docs) < 100:
            break
        offset += 100
        time.sleep(0.2)
    npl = [d for d in series if d["series_code"].endswith(".FSANL_PT")
           and re.match(r"^[AQ]\.[A-Z]{2}\.FSANL_PT$", d["series_code"])]
    print(f"FSI: {len(series)} series listed, {len(npl)} NPL ratio series (A+Q)")

    # 2) fetch observations in batches
    rows, meta = [], {}
    codes = [d["series_code"] for d in npl]
    by_code = {d["series_code"]: d for d in npl}
    B = 20
    for i in range(0, len(codes), B):
        batch = codes[i:i + B]
        r = S.get(f"{base}/series",
                  params={"series_ids": ",".join(f"IMF/FSI/{c}" for c in batch),
                          "observations": 1, "format": "json"}, timeout=90)
        r.raise_for_status()
        for doc in r.json()["series"]["docs"]:
            code = doc["series_code"]
            name = by_code[code]["series_name"]
            freq, cty = code.split(".")[0], code.split(".")[1]
            country = name.split("–")[1].strip() if "–" in name else cty
            per, val = doc.get("period", []), doc.get("value", [])
            n_obs = 0
            for p, v in zip(per, val):
                if v is None:
                    continue
                rows.append({"freq": freq, "iso2": cty, "country": country,
                             "period": p, "npl_pct": v})
                n_obs += 1
            m = meta.setdefault(cty, {"country": country})
            m[per and max(p for p, v in zip(per, val) if v is not None) or ""] = None
        time.sleep(0.4)
    rows.sort(key=lambda x: (x["iso2"], x["freq"], x["period"]))
    out = DATA / "imf_fsi_npl.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["freq", "iso2", "country", "period", "npl_pct"])
        w.writeheader()
        w.writerows(rows)
    print(f"FSI: {len(rows)} obs, {len({r['iso2'] for r in rows})} countries -> {out}")

    # 3) summary: best freq per country (Q preferred), latest obs
    summary = []
    for cty in sorted({r["iso2"] for r in rows}):
        sub = [r for r in rows if r["iso2"] == cty]
        q = [r for r in sub if r["freq"] == "Q"]
        best = q if q else [r for r in sub if r["freq"] == "A"]
        last = best[-1]
        summary.append({"iso2": cty, "country": last["country"], "best_freq": last["freq"],
                        "latest_period": last["period"], "latest_npl_pct": last["npl_pct"],
                        "n_quarterly_obs": len(q)})
    outs = DATA / "imf_fsi_npl_summary.csv"
    with outs.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["iso2", "country", "best_freq", "latest_period",
                                          "latest_npl_pct", "n_quarterly_obs"])
        w.writeheader()
        w.writerows(summary)
    print(f"FSI summary: {len(summary)} countries -> {outs}")
    for c in ("US", "CN", "IN", "GB", "JP", "DE"):
        s = [x for x in summary if x["iso2"] == c]
        if s:
            s = s[0]
            print(f"   {c}: {s['best_freq']} {s['latest_period']} = {s['latest_npl_pct']:.3f} "
                  f"(Q-obs: {s['n_quarterly_obs']})")
    return rows

if __name__ == "__main__":
    fetch_wb_npl()
    fetch_fsi_npl()
