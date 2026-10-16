"""Dossier-11 probe round 3: remaining pins — NFC gross income (FRED), DPI quarterly,
OECD + ONS mirrors (DBnomics), IMF GFS SDMX, WDI gov revenue/interest, ONS beta API,
Japan ESRI.

Run: uv run python scripts/probe11_global.py
"""

import asyncio
import os

import httpx

FRED = "https://api.stlouisfed.org/fred"
DBN = "https://api.db.nomics.world/v22"
WDI = "https://api.worldbank.org/v2"
IMF_SDMX = "https://api.imf.org/external/sdmx/2.1"
UA = {"User-Agent": "debt-monitor-probe/0.1 (research)"}


def load_key() -> str:
    for line in open(".env"):  # noqa: SIM115
        if line.startswith("FRED_API_KEY="):
            return line.split("=", 1)[1].strip()
    return os.environ.get("FRED_API_KEY", "")


async def fred_search(client, key, text, limit=8):
    try:
        r = await client.get(
            f"{FRED}/series/search",
            params={"search_text": text, "api_key": key, "file_type": "json", "limit": limit, "order_by": "popularity", "sort_order": "desc"},
            headers=UA,
            timeout=30,
        )
        if r.status_code != 200:
            print(f"[FRED '{text}'] HTTP {r.status_code}")
            return
        print(f"\n[FRED '{text}']")
        for s in r.json().get("seriess", []):
            print(f"  {s['id']:<22} {s['frequency'][:9]:<10} {s['seasonal_adjustment_short']:<5} {s['observation_end'][:7]} {s['title'][:70]}")
    except Exception as exc:  # noqa: BLE001
        print(f"[FRED '{text}'] ERROR {type(exc).__name__}")
    await asyncio.sleep(1.6)


async def main() -> None:
    key = load_key()
    async with httpx.AsyncClient() as client:
        # --- FRED remaining pins ---
        await fred_search(client, key, "disposable personal income SAAR quarterly BEA")
        await fred_search(client, key, "gross operating surplus corporate quarterly")
        await fred_search(client, key, "gross value added corporate business quarterly")

        # --- DBnomics: OECD + ONS dataset discovery (datasets endpoint returns dict) ---
        for prov in ("ONS", "OECD"):
            r = await client.get(f"{DBN}/datasets/{prov}", params={"limit": 1000}, headers=UA, timeout=90)
            js = r.json()
            dsets = js.get("datasets", {})
            items = dsets.items() if isinstance(dsets, dict) else [(d.get("code"), d) for d in dsets]
            print(f"\n[DBn {prov}] datasets: {len(items)}")
            for code, d in items:
                name = str(d.get("name", "")) if isinstance(d, dict) else ""
                if prov == "ONS" or any(
                    k in name.lower() for k in ("sector account", "national accounts", "household", "government finance", "disposable")
                ):
                    print(f"  {code:<26} {name[:75]}")

        # --- IMF GFS SDMX: does the dataflow exist and serve interest? ---
        for path in ("/dataflow/all/all/latest", "/data/GFS/all?detail=dataonly&startPeriod=2023"):
            try:
                r = await client.get(f"{IMF_SDMX}{path}", headers=UA, timeout=90)
                print(f"\n[IMF {path}] HTTP {r.status_code} len={len(r.text)}")
                print("  " + r.text[:400].replace("\n", " ")[:400])
            except Exception as exc:  # noqa: BLE001
                print(f"[IMF {path}] ERROR {type(exc).__name__}: {exc}")

        # --- WDI: gov revenue + interest candidates ---
        for indicator in ("GC.REV.XGRT.GD.ZS", "GC.INTP.TOTL.GD.ZS", "GC.XPN.TOTL.GD.ZS", "GC.TAX.TOTL.GD.ZS", "GC.DOD.TOTL.GD.ZS"):
            try:
                r = await client.get(f"{WDI}/country/DE;US;IN;CN/indicator/{indicator}", params={"format": "json", "date": "2023:2025"}, headers=UA, timeout=60)
                js = r.json()
                n = js[0].get("total", 0) if isinstance(js, list) else 0
                sample = [(d["countryiso3code"], d["date"], d["value"]) for d in (js[1] if isinstance(js, list) and len(js) > 1 else []) if d.get("value")][:4]
                print(f"[WDI {indicator}] HTTP {r.status_code} total={n} sample={sample}")
            except Exception as exc:  # noqa: BLE001
                print(f"[WDI {indicator}] ERROR {type(exc).__name__}")

        # --- ONS beta API ---
        for url in (
            "https://api.beta.ons.gov.uk/v2/datasets",
            "https://api.beta.ons.gov.uk/v2/datasets/sector-accounts/editions",
        ):
            try:
                r = await client.get(url, headers=UA, timeout=60)
                print(f"\n[ONS beta {url}] HTTP {r.status_code} len={len(r.text)}")
                print("  " + r.text[:300].replace("\n", " "))
            except Exception as exc:  # noqa: BLE001
                print(f"[ONS beta {url}] ERROR {type(exc).__name__}")

        # --- Japan ESRI: SNA landing reachability ---
        try:
            r = await client.get("https://www.esri.cao.go.jp/en/sna/data/sna_kakuhou_e.html", headers=UA, timeout=60)
            print(f"\n[ESRI] HTTP {r.status_code} len={len(r.text)}")
            import re

            xls = sorted(set(re.findall(r'href="([^"]+\.(?:xlsx|xls|csv|zip))"', r.text, re.I)))
            print(f"  file links: {xls[:10]}")
        except Exception as exc:  # noqa: BLE001
            print(f"[ESRI] ERROR {type(exc).__name__}")


if __name__ == "__main__":
    asyncio.run(main())
