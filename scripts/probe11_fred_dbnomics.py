"""Dossier-11 probe: FRED series pins (US income + interest payments) and
DBnomics mirrors (Fed Z.1 interest-paid lines, OECD sector accounts, ONS).

Run: uv run python scripts/probe11_fred_dbnomics.py
"""

import asyncio
import os

import httpx

FRED = "https://api.stlouisfed.org/fred"
DBN = "https://api.db.nomics.world/v22"
UA = {"User-Agent": "debt-monitor-probe/0.1 (research)"}

# concept -> search text (FRED series/search)
FRED_SEARCHES = {
    "DPI quarterly": "disposable personal income quarterly",
    "personal interest payments": "personal interest payments",
    "federal interest payments": "federal government interest payments",
    "gen-gov interest": "government interest paid",
    "corp net interest": "net interest corporate business",
    "GOS corporate": "gross operating surplus corporate",
}

Z1_SEARCHES = {"HH interest paid": "interest paid households", "NFC interest paid": "interest paid nonfinancial corporate"}


async def fred_search(client: httpx.AsyncClient, key: str, text: str) -> None:
    try:
        r = await client.get(
            f"{FRED}/series/search",
            params={"search_text": text, "api_key": key, "file_type": "json", "limit": 12, "order_by": "popularity", "sort_order": "desc"},
            headers=UA,
        )
        docs = r.json().get("seriess", [])
        print(f"\n[FRED search '{text}'] {len(docs)} hits")
        for s in docs:
            print(f"  {s['id']:<22} {s['frequency']:<12} {s['seasonal_adjustment_short']:<6} {s['observation_start'][:4]}->{s['observation_end'][:4]} {s['title'][:70]}")
    except Exception as exc:  # noqa: BLE001
        print(f"[FRED search '{text}'] ERROR {exc}")
    await asyncio.sleep(0.4)


async def fred_obs(client: httpx.AsyncClient, key: str, series: str) -> None:
    try:
        r = await client.get(
            f"{FRED}/series/observations",
            params={"series_id": series, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": 3},
            headers=UA,
        )
        obs = [o for o in r.json().get("observations", []) if o.get("value") not in (".",)]
        got = [(o["date"], o["value"]) for o in obs]
        print(f"  obs {series}: {got}")
    except Exception as exc:  # noqa: BLE001
        print(f"  obs {series}: ERROR {exc}")
    await asyncio.sleep(0.3)


async def dbn_search(client: httpx.AsyncClient, dataset: str, q: str) -> None:
    try:
        r = await client.get(
            f"{DBN}/series/{dataset}",
            params={"q": q, "limit": 8, "observations": 0, "format": "json"},
            headers=UA,
            timeout=60,
        )
        docs = r.json().get("series", {}).get("docs", [])
        print(f"\n[DBnomics {dataset} '{q}'] {len(docs)} hits")
        for d in docs:
            print(f"  {d.get('series_code', ''):<28} {d.get('indexed_at', '')[:10]} {d.get('series_name', '')[:80]}")
    except Exception as exc:  # noqa: BLE001
        print(f"[DBnomics {dataset} '{q}'] ERROR {exc}")
    await asyncio.sleep(0.4)


async def dbn_providers(client: httpx.AsyncClient) -> None:
    r = await client.get(f"{DBN}/providers", headers=UA, timeout=60)
    provs = {p["code"]: (p.get("indexed_at", "")[:10], p.get("nb_series", 0)) for p in r.json().get("providers", [])}
    for code in ("ONS", "OECD", "ESRI", "STAT_JP", "CAS"):
        print(f"provider {code}: {provs.get(code, 'ABSENT')}")


async def main() -> None:
    key = os.environ.get("FRED_API_KEY", "")
    # load .env manually (probes stay dependency-free)
    if not key:
        for line in open(".env"):  # noqa: SIM115
            if line.startswith("FRED_API_KEY="):
                key = line.split("=", 1)[1].strip()
    async with httpx.AsyncClient() as client:
        for _label, text in FRED_SEARCHES.items():
            await fred_search(client, key, text)
        print("\n[FRED obs checks]")
        for s in ("A091RC1Q027SBEA", "W163RC1Q027SBEA", "A067RC1Q027SBEA", "W213RC1Q027SBEA", "BOGZ1FL153165105Q", "BOGZ1FA153045005Q"):
            await fred_obs(client, key, s)

        for _label, q in Z1_SEARCHES.items():
            await dbn_search(client, "FED/Z1", q)
        await dbn_providers(client)
        # OECD household disposable income datasets on the mirror
        await dbn_search(client, "OECD/NAAG", "disposable income")
        await dbn_search(client, "OECD/NAMICS", "household disposable income")
        # ONS datasets (mirror)
        r = await client.get(f"{DBN}/datasets/ONS", headers=UA, timeout=60)
        dsets = r.json().get("datasets", [])
        print(f"\nONS datasets on mirror: {len(dsets)}")
        for d in dsets[:25]:
            print(f"  {d.get('code', ''):<28} {str(d.get('name', ''))[:70]}")


if __name__ == "__main__":
    asyncio.run(main())
