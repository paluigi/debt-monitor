# Debt Monitor — Data-Source Research Overview

**Scope**: identify and verify open / free-tier data sources for (1) government and private debt volumes, (2) debt-health metrics, (3) CPI/HICP deflators and nominal GDP normalizers, (4) government and corporate yields — across as many countries as possible (US, euro area, UK, Japan, China, India, …), aiming for data updated **at least monthly** (quarterly accepted; annual only as documented fallback).

**Method**: every candidate source was probed live on **2026-08-19** with single-file Python `requests` scripts — no claim in these documents rests on documentation or third-party summaries alone. "Latest obs" always means the newest observation actually seen in a response body. Detailed evidence lives in [sources/](sources/) (six dossiers + index).

**Verdict on the shared AI memo**: the recommended stack (BIS/IMF/FRED/ECB backbone) survives validation, but several specifics were wrong or stale — see §5.

---

## 1. Coverage snapshot — what a real dashboard can show today

All numbers below were read from live responses on 2026-08-19.

| Block | Best cross-country source | Countries | Freq | Latest obs seen |
|---|---|---|---|---|
| Government debt stock | BIS Total Credit (gov sector) | 48 (US/CN/IN/JP/GB/DE/FR/IT + EA) | Quarterly | 2025-Q4 |
| Government debt stock (annual breadth) | IMF WEO `GGXWDG_NGDP` / GDD `FL_S13_POGDP_PT` | 207 / 190 | Annual | 2025 / 2024 |
| Private debt stock (HH + NFC) | BIS Total Credit | 43 (both HH+NFC; CN ¥81.3tn HH, IN ₹161.6tn HH) | Quarterly | 2025-Q4 |
| US private debt detail | Fed Z.1 (via DBnomics) + H.8 weekly | US | Quarterly / Weekly | 2026-Q1 / 2026-08-05 |
| Euro-area private debt detail | ECB BSI (monthly loans HH/NFC) + QSA (stocks) | EA + members | Monthly / Quarterly | 2026-06 / 2025-Q4 |
| Debt health — cross-country | IMF FSI quarterly NPL (~100 countries; CN 2025-Q1=1.513, IN=2.344) | ~100 | Quarterly | 2025-Q1 |
| Debt health — early warning | BIS DSR (HH & private non-financial) | 32 | Quarterly | 2025-Q4 |
| Debt health — US detail | FRED delinquency/charge-off (7 series) | US | Quarterly | 2026-Q1 |
| CPI deflator | FRED CPIAUCSL (US); Eurostat `prc_hicp_minr` (EA, ECOICOP v2; ECB ICP frozen 2025-12); IFS PCPI_IX (GB/JP/CN/IN, mirror-lagged) | Global | Monthly | 2026-07 (US) / **2026-07 (EA)** / 2025-06~07 (IFS) |
| Nominal GDP | FRED GDP (US); IFS NGDP_SA_XDC (GB/JP/IN quarterly; CN annual-only) | Global | Quarterly / Annual | 2026-Q2 (US) / 2025-Q1/Q2 (IFS) |
| Government yields | US Treasury CSV; ECB YC U2; Japan MoF; BoE GLC | US/EA/JP/UK | Daily | 2026-08-18 |
| Corporate yields / stress | ICE BofA via FRED: BAMLC0A0CM/H0A0HYM2 + EUR OAS pair | US + EUR | Daily | 2026-08-18 |
| Bank lending rates | ECB MIR (EA NFC new-loan rate 2026-06=4.11); FRED MORTGAGE30US 2026-08-13=6.67 | EA / US | Monthly / Weekly | fresh |

Structural gaps with no login-free source (documented in dossiers 03/06): China daily CGB curve, India daily G-sec curve, NY Fed HHDC/BoE IADB/EBA dashboard (JS-gated), RBI DBIE (registration), US state-local debt (Census annual scrape), Eurostat quarterly EDP table (API serves annual only).

## 2. Validation of the prior AI memo — verdicts

| Claim | Verdict |
|---|---|
| BIS Total Credit "CSV/REST API, 40+ economies" | ✅ Data true (48 countries, quarterly, gov/HH/NFC, %GDP) — **but** old bulk URL is dead; working: `data.bis.org/static/bulk/WS_TC_csv_col.zip`. SDMX data queries unresolved (404s); use bulk. |
| IMF GDD "190 countries, open API" | ✅ via `api.imf.org/external/sdmx/2.1` (claimed datamapper URL is Akamai-blocked). Annual only. **CN/IN private-sector cells are NA** — BIS covers those. |
| FRED "gold standard, aggregates OECD/BIS international stats" | ⚠️ **Half-true and dangerous**: US series are excellent and fresh, but OECD-MEI-sourced series froze at 2024-03/2024-01 (CPI GB/IN, yields) or 404; BIS-sourced debt IDs are gone. Use FRED for US + market spreads only. |
| World Bank NPL "excellent global proxy" | ⚠️ True for breadth (217 economies) but **annual** — fails the monthly rule; IMF FSI quarterly is the cadence fix (same underlying data). |
| China & India NPL "via WB/FRED/DBnomics" | ✅ via WB (annual) + DBnomics IMF/FSI quarterly (CN/IN to 2025-Q1); FRED has nothing. |
| ICE BofA yields "free on FRED, great crisis indicator" | ✅ Verified live through 2026-08-18 (US IG 0.82 / HY 2.75; EUR IG OAS 1.40 / HY OAS 2.55). Sanity-check levels before display (look compressed). YTM-variant IDs are 404s. |
| FRED international yields "IRLTLT01xxx" | ⚠️ Partially true: DE/JP/GB/US live (2026-06, monthly) but **CN/IN do not exist**; DBnomics OECD mirrors are stale (2023-12/2024-01). |
| ECB euro-area corporate bond yields | ❌ **Does not exist** as claimed — the "BLBC_C BBB corporate" key was fabricated (`KR` = key interest rate). Use FRED ICE BofA EUR OAS. |
| yfinance ETF proxies | ✅ Works (US tickers) but proxy-only; grey-zone ToS — fallback, not backbone. |
| ECB "Supervisory Banking Statistics SDMX/CSV" | ⚠️ Partially: not on ECB data-api (SBS flow 404); the working machine path is the **DBnomics `ECB/SUP` mirror** (NPE stocks, 2026-Q1). |
| DBnomics aggregator | ✅ Keyless 93 providers — but mirror lags (BIS ~3 quarters, IFS ~13 months) and some broken dataset listings; great for prototyping, prefer upstream in production. |

## 3. Recommended source stack (per domain)

**Volumes (core dashboard)**
- BIS WS_TC bulk quarterly — 48 countries × {gov, HH, NFC, private-total} × {XDC, USD, %GDP}: one 674 KB zip, the single most valuable download.
- US: Z.1 via DBnomics `FED/Z1` (per-instrument detail) + H.8 weekly momentum; Treasury debt-to-penny **daily** (freshest gov-debt series found).
- Euro area: ECB BSI monthly (loans by sector) + QSA quarterly stocks (REF_AREA `I9`, STO `LE`).
- Annual breadth/backfill: IMF WEO (207) + GDD (190); Eurostat EDP (EA/EU annual 2025 published).

**Health**
- BIS DSR quarterly (the early-warning workhorse) + IMF FSI quarterly NPL (cross-country) + FRED US delinquency detail + ECB SUP NPE via DBnomics. WB NPL annual as documented fallback.

**Deflators / normalizers**
- US: FRED CPIAUCSL + GDP. EA: **Eurostat `prc_hicp_minr`** (ECOICOP v2 since 2026-01: dim `coicop18`, all-items `TOTAL`, geo `EA` changing composition, index `I25`/rates `RCH_A`; full history 1997→2026-07 — the v1 datasets `manr`/`aind` and ECB ICP are frozen at 2025-12). Non-EU: IFS via DBnomics (accept ~13-month mirror lag for CN/IN/JP/GB, or map national SDMX later).

**Yields**
- Daily curves: US Treasury CSV; ECB YC (U2, G_N_A=AAA vs G_N_C=all-ratings — note the semantics!); Japan MoF (SJIS); BoE GLC zip. Monthly cross-check: FRED IRLTLT01 (no CN/IN). Corporate: ICE BofA via FRED (US IG/HY + EUR OAS); ECB MIR for bank lending rates; FRED MORTGAGE30US.

## 4. Recommended acquisition architecture (proposal)

```
collectors/                    # one module per provider, thin adapters
  bis.py          -> WS_TC + WS_DSR bulk zips (quarterly, ~40MB/yr)
  imf.py          -> GDD/WEO via api.imf.org SDMX (annual)
  imf_fsi.py      -> FSI NPL via DBnomics (quarterly)
  fred.py         -> fredgraph.csv over plain HTTP+curl-UA (US detail)
  ecb.py          -> BSI/MIR/ICP/YC/QSA via data-api.ecb.europa.eu (monthly/daily)
  eurostat.py     -> HICP manr/aind + EDP annual + namq (once pinned)
  treasury.py     -> fiscaldata debt_to_penny (daily)
  dbnomics.py     -> FED/Z1, FED/H8, IMF/IFS, ECB/SUP mirrors
storage: parquet per (source, dataset), partitioned by period
scheduler: quarterly anchors (BIS/IMF) + monthly (ECB/Eurostat/IFS) + daily (yields) + weekly (H.8, MORTGAGE30US)
```

Key engineering notes from probing: host-level quirks are the main risk (FRED HTTPS, BIS host move, Akamai blocks, JSON-stat flattened-index parsing, ECB key semantics like `I9`/`Z01`/6-digit `000000`, SJIS decoding for MoF). All documented per-card.

## 5. Open items for the next phase

1. Pin Eurostat `namq_10_gdp` / `nasq_10_f_bs` series filters (both returned nulls/400 under probed combos — one browser session against the Eurostat table browser should resolve).
2. ~~HICP API lag puzzle~~ **Resolved**: the 2025-12 frontier was the **ECOICOP v2 classification break** — new dataset `prc_hicp_minr` (dim `coicop18`, code `TOTAL`) serves 1997-01→2026-07 continuously; v1 datasets and ECB ICP keys are frozen at 2025-12 (re-probe ECB for a v2 key family before 2026 use).
3. JS-gated sources (NY Fed HHDC, BoE IADB, EBA dashboard): one Browser Use session per quarter to resolve file URLs, then keyless download.
4. China/India daily yield curves + PBOC TSF split: decide between registration (RBI DBIE), licensed vendor, or headless scraping — or accept BIS/IFS cadence.
5. OECD PSD dimension mapping (quarterly gov debt workaround for EU/UK/JP) before trusting its %GDP series.
6. Eurostat EDP quarterly: confirm whether a different table code serves the quarterly EDP notification data via API.
7. First datasets acquired: World Bank NPL annual (154 economies → `data/wb_npl_annual.csv`) and IMF FSI NPL quarterly+annual (152 countries, CN/IN through 2025-Q1 → `data/imf_fsi_npl.csv`) via `scripts/acquire_npl.py`.
8. Decisions pending (dossier 08): NY Fed HHDC manual download (recommended), RBI DBIE registration for India yields (recommended), EBA dashboard (optional), BoE IADB / ChinaBond (defer).
