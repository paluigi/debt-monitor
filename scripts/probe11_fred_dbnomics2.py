"""Dossier-11 probe round 2: FRED (slower pacing) + DBnomics detail.

Run: uv run python scripts/probe11_fred_dbnomics2.py
"""

import asyncio
import os

import httpx

FRED = "https://api.stlouisfed.org/fred"
DBN = "https://api.db.nomics.world/v22"
UA = {"User-Agent": "debt-monitor-probe/0.1 (research)"}

FRED_SEARCHES = {
    "DPI quarterly SAAR": "personal income disposition disposable quarterly",
    "personal interest payments": "personal interest payments",
    "federal interest payments": "federal government interest payments",
    "gov interest paid": "government interest paid",
    "corp net interest": "net interest and miscellaneous payments",
    "personal saving": "personal saving quarterly",
}


def load_key() -> str:
    for line in open(".env"):  # noqa: SIM115
        if line.startswith("FRED_API_KEY="):
            return line.split("=", 1)[1].strip()
    return os.environ.get("FRED_API_KEY", "")


async def fred_search(client: httpx.AsyncClient, key: str, text: str) -> None:
    for attempt in range(3):
        try:
            r = await client.get(
                f"{FRED}/series/search",
                params={"search_text": text, "api_key": key, "file_type": "json", "limit": 10, "order_by": "popularity", "sort_order": "desc"},
                headers=UA,
                timeout=30,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[FRED '{text}'] NET ERROR attempt {attempt}: {type(exc).__name__}")
            await asyncio.sleep(4)
            continue
        if r.status_code == 200:
            docs = r.json().get("seriess", [])
            print(f"\n[FRED '{text}']", flush=True)
            for s in docs:
                print(f"  {s['id']:<22} {s['frequency'][:9]:<10} {s['seasonal_adjustment_short']:<5} {s['observation_end'][:7]} {s['title'][:66]}")
            break
        print(f"[FRED '{text}'] HTTP {r.status_code} attempt {attempt}: {r.text[:80]}")
        await asyncio.sleep(3)
    await asyncio.sleep(1.5)


async def fred_obs(client: httpx.AsyncClient, key: str, series: str) -> None:
    try:
        r = await client.get(
            f"{FRED}/series/observations",
            params={"series_id": series, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": 4},
            headers=UA,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  obs {series}: NET ERROR {type(exc).__name__}")
        return
    if r.status_code != 200:
        print(f"  obs {series}: HTTP {r.status_code}")
        return
    obs = [o for o in r.json().get("observations", []) if o.get("value") != "."]
    print(f"  obs {series}: {[(o['date'], o['value']) for o in obs]}")
    await asyncio.sleep(1.5)


async def dbn_series(client: httpx.AsyncClient, dataset: str, q: str, full: bool = False) -> None:
    r = await client.get(f"{DBN}/series/{dataset}", params={"q": q, "limit": 10, "observations": 0, "format": "json"}, headers=UA, timeout=60)
    docs = r.json().get("series", {}).get("docs", [])
    print(f"\n[DBn {dataset} '{q}']")
    for d in docs:
        name = d.get("series_name", "") if full else d.get("series_name", "")[:110]
        print(f"  {d.get('series_code', ''):<24} {name}")


async def main() -> None:
    key = load_key()
    async with httpx.AsyncClient() as client:
        # FRED concepts, with pinned-candidate obs checks
        for _label, text in FRED_SEARCHES.items():
            await fred_search(client, key, text)
        print("\n[FRED obs pins]")
        for s in (
            "A067RC1Q027SBEA",  # old DPI/saving
            "DPI",  # monthly DPI
            "A091RC1Q027SBEA",  # federal interest payments candidate
            "W163RC1Q027SBEA",  # personal interest payments candidate
            "W213RC1Q027SBEA",  # corp net interest candidate
            "A213RC1Q027SBEA",
        ):
            await fred_obs(client, key, s)

        # Z.1: full names + latest obs of the interest series
        await dbn_series(client, "FED/Z1", "interest paid households and nonprofit", full=True)
        await dbn_series(client, "FED/Z1", "interest paid nonfinancial corporate", full=True)
        await dbn_series(client, "FED/Z1", "interest paid federal government", full=True)
        await dbn_series(client, "FED/Z1", "interest paid state local governments", full=True)
        r = await client.get(
            f"{DBN}/series",
            params={"series_ids": "FED/Z1/FA156130005.Q,FED/Z1/FA106130001.Q,FED/Z1/FA106130003.Q", "observations": 1, "format": "json"},
            headers=UA,
            timeout=90,
        )
        print("\n[DBn Z.1 interest obs]")
        for doc in r.json().get("series", {}).get("docs", []):
            periods = doc.get("period", [])
            values = doc.get("value", [])
            tail = [(str(p), v) for p, v in list(zip(periods, values, strict=False))[-3:] if v is not None]
            print(f"  {doc.get('series_code', '')}: {doc.get('series_name', '')[:80]} -> {tail}")

        # providers list shape + OECD/ONS dataset discovery
        r = await client.get(f"{DBN}/providers", headers=UA, timeout=60)
        js = r.json()
        print("\nproviders keys:", list(js.keys()))
        provs = js.get("providers", {})
        if isinstance(provs, dict):
            codes = list(provs.keys())
        else:
            codes = [p.get("code") for p in provs]
        for want in ("ONS", "OECD", "ESRI"):
            hit = [c for c in codes if c and want in str(c)]
            print(f"  provider containing '{want}': {hit}")

        r = await client.get(f"{DBN}/datasets/ONS", headers=UA, timeout=60)
        print("\nONS datasets:", len(r.json().get("datasets", [])))
        for d in r.json().get("datasets", [])[:30]:
            print(f"  {d.get('code', ''):<24} {str(d.get('name', ''))[:70]}")

        r = await client.get(f"{DBN}/datasets/OECD", params={"limit": 500}, headers=UA, timeout=90)
        dsets = r.json().get("datasets", [])
        print(f"\nOECD datasets on mirror: {len(dsets)}")
        for d in dsets:
            name = str(d.get("name", "")).lower()
            if any(k in name for k in ("sector account", "national accounts", "household debt", "disposable")):
                print(f"  {d.get('code', ''):<24} {str(d.get('name', ''))[:70]}")


if __name__ == "__main__":
    asyncio.run(main())
