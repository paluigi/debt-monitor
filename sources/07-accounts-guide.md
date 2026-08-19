# Sources 07 — Account Setup Guide (free tiers, keys, registrations)

Which accounts are actually worth creating to unlock data beyond the keyless sources already verified in dossiers 01–06, with step-by-step signup instructions. All free. Created once, stored as env vars, used by the collectors.

**Priority order** is driven by the value each account unlocks for the crisis-monitoring goal (see dossier 08 for the JS-gated trade-off analysis).

---

## 1. FRED API key (US data) — RECOMMENDED, 2 minutes

The single highest-value registration: replaces the fragile plain-HTTP+curl-UA workaround for `fredgraph.csv` (verified working but rate-limited and HTTP-only, dossier 01) with the official JSON API over HTTPS. Unlocks **bulk metadata queries** (`/fred/series/observations?series_id=…&api_key=…`) and the full 800k+ series catalog search — needed to systematically find US state/local debt IDs (a verified gap) and any series family we haven't enumerated.

**Steps**:
1. Go to <https://fred.stlouisfed.org/docs/api/api_key.html>
2. Sign up with email + a short description ("debt-monitor dashboard"), accept terms.
3. Key arrives by email within minutes. Note: FRED keys are tied to your email; there is no per-key quota dashboard — the limit is fair-use (~120 req/min soft, bursts fine for our volumes).
4. Store: `FRED_API_KEY=...` (env var; collectors read via `os.environ`).

**What it unlocks**: all FRED series via HTTPS JSON (delinquency DRCCLACBS…, GFDEBTN, DGS curves, ICE BofA spreads, MORTGAGE30US, plus systematic state/local discovery). No other account needed for US data.

## 2. RBI DBIE (India) — RECOMMENDED if India is a priority

The only programmatic route to India's official granularity: sectoral deployment of bank credit (household vs industry vs services), weekly statistical supplement, G-sec yields, on-tap historical bulk. Free, but requires registration and data-use confirmation.

**Steps**:
1. Go to <https://dbie.rbi.org.in/DBIE/dbie.rbi?site=home> → "Register" (individual researcher; email + name + purpose; may ask for organization).
2. Verify email, log in.
3. First login: accept the data-use policy popup (permitted non-commercial use with attribution).
4. Bulk downloads: browse to a report (e.g. *Sectoral Deployment of Bank Credit*, monthly) → "Download" → CSV/XLSX for a date range. API: DBIE exposes a REST API for registered users (token issued under your profile); see the "API" tab post-login.
5. Store: `DBIE_TOKEN=...` once issued.

**What it unlocks**: India monthly credit split (currently only BIS quarterly aggregate, dossier 03) + G-sec daily yields (verified gap, dossier 06) + WSS weekly aggregates. **Highest-value registration after FRED.**

## 3. OECD Data Explorer (optional)

Most OECD data is keyless via SDMX (dossier 01); an account adds saved queries + larger extract limits on the Data Explorer UI. Only worth it if we adopt OECD PSD quarterly government debt (the EU/UK/JP workaround, dossier 02) and its dimension mapping proves painful — the API itself stays keyless.

**Steps**: <https://data-explorer.oecd.org/> → sign in → "Save query". No key management.

## 4. IMF SDMX (no account needed — clarification)

`api.imf.org/external/sdmx/2.1` is fully keyless (verified, dossiers 01/02). The old *IMF SDMX API* registration page (valid for the legacy `dataservices.imf.org` ) is NOT needed for our endpoints. Skip.

## 5. World Bank / Eurostat / ECB / BIS / Treasury / DBnomics — all keyless

Verified keyless in dossiers 01–06: World Bank API, Eurostat dissemination API, ECB data-api, BIS bulk zips, US Treasury FiscalData, DBnomics v22, Japan MoF CSVs, BoE GLC zip. No accounts.

## 6. Sources NOT worth registering (avoid)

- **Investing.com / Trading Economics / Refinitiv / Bloomberg**: commercial licenses, not free tiers — out of scope.
- **ChinaBond / CFETS chinamoney**: institutional registration; the public view is the JS portal anyway (dossier 06). Use akshare fallback or accept the gap.
- **ICE Direct**: ICE BofA indices are available free via FRED (verified, dossier 06) — registering with ICE directly buys nothing extra.
- **FINRA TRACE**: the free "Fixed Income Data" page moved/404'd during probing (dossier 06); historical TRACE via CMDS requires a free FINRA account — marginal value since FRED ICE OAS covers US credit stress.

## Summary table

| Account | Effort | Unlocks | Priority |
|---|---|---|---|
| FRED API key | 2 min, email only | Official US API (HTTPS, search, all series) | **High** — do now |
| RBI DBIE | 5 min + email verify | India credit split + G-sec yields | **High** if India matters |
| FINRA (CMDS) | 5 min | Historical TRACE aggregates | Low |
| OECD Data Explorer | 2 min | Saved queries (API keyless anyway) | Low |
| IMF SDMX / WB / Eurostat / ECB / BIS / Treasury / DBnomics | 0 | — (keyless) | — |
