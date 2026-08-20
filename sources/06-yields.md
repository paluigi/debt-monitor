# Debt Monitor — Source Dossier 06: Government & Private Debt YIELDS

Benchmark government yield curves (all maturities) + investment-grade/high-yield corporate bond yields + real-economy borrowing-cost links (mortgage, bank lending rates) for US, euro area, UK, Japan, China, India.

All probes run 2026-08-19 (UTC) with Python `requests` (fetch+parse in one script, no shell pipes). "Last obs" = latest observation actually seen in the response body. US/euro-area/Japan/UK daily curves are same-day fresh (T or T+1); corporate indices are daily; China and India daily curves are the two structural gaps.

---

## US Treasury — Daily Treasury Par Yield Curve (official)

- **What**: Daily CMT par yields, 1/1.5/2/3/4/6 Mo, 1/2/3/5/7/10/20/30 Yr. The sovereign benchmark for the US.
- **Coverage**: US federal government curve, 1990–present (per-year files), full maturity grid.
- **Frequency & lag**: Daily (business days), published ~5pm ET same day.
- **Access (exact endpoint + Python)**: Keyless CSV per year:
  `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve&field_tdr_date_value=2026&page&_format=csv`
  `requests.get(url)` → `csv.DictReader(io.StringIO(r.text))`. Rows are **newest-first** (row 0 = latest). XML variant: `.../daily-treasury-rates.xml/2026/all?...&_format=xml`.
- **License & cost**: Public domain (US federal government). Free, no key.
- **Sample series**: `daily_treasury_yield_curve 2026` → last row 08/18/2026: 10 Yr = 4.71, 2 Yr = 4.19 (approx; row shows full grid), 158 YTD rows.
- **Verified**: **Verified live 2026-08-19** — HTTP 200, 158 rows, first row date 08/18/2026, 10Y=4.71.
- **Notes & pitfalls**: The old `home.treasury.gov/XML/dailyrates...` paths 404; use the `.csv/{year}/all` pattern above. Watch the header "1.5 Month" column (has a space → DictReader key). Holiday rows absent.

## FRED (St. Louis Fed) — US Treasury daily yields (DGS family)

- **What**: Daily Treasury constant-maturity yields mirrored from Treasury: `DGS3MO, DGS2, DGS10, DGS30`, plus spreads `T10Y3M`, breakevens `T10YIE`.
- **Coverage**: US, 1962/1976–present depending on tenor.
- **Frequency & lag**: Daily; FRED lags Treasury by 1 business day.
- **Access**: Keyless CSV: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10` → parse two-column CSV (DATE,value). Add `&cosd=YYYY-MM-DD` for start date (full history default ≈ last 3–5 yrs per series but `cosd` extends).
- **License & cost**: Free, keyless; FRED terms of use (attribution).
- **Sample series seen**:
  - `DGS2` last **2026-08-17 = 4.19**
  - `DGS10` last **2026-08-17 = 4.72**
  - `DGS30` last **2026-08-17 = 5.31**
  - `DGS3MO` last **2026-08-17 = 3.87**
  - `T10Y3M` last **2026-08-18 = 0.85`; `T10Y2YM` (monthly avg) last 2026-07-01 = 0.38
- **Verified**: **Verified live 2026-08-19** — all above HTTP 200 with values.
- **Notes & pitfalls**: **`T10Y2M` returns HTTP 404** — discontinued (Treasury 2-month CMT feed ended); compute 10Y−2Y from DGS10−DGS2 or use T10Y3M. FRED can rate-limit: one fredgraph fetch in this session hit ReadTimeout — retry/backoff and keep batches small.

## FRED — ICE BofA US Corporate IG & High Yield Effective Yields (prior claim 1)

- **What**: `BAMLC0A0CM` (US Corporate Index effective yield, IG) and `BAMLH0A0HYM2` (US High Yield Index effective yield) — the classic crisis-spread indicators. Plus EUR corporates OAS: `BAMLEMCBPIOAS` (Euro corporates IG OAS), `BAMLHE00EHYIOAS` (Euro high yield OAS).
- **Coverage**: US + EUR ICE BofA index families, daily from 1996–97.
- **Frequency & lag**: Daily, T+1.
- **Access**: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLC0A0CM` (same pattern for the others), keyless two-column CSV.
- **License & cost**: Free via FRED; underlying indices © ICE BofA — FRED terms apply (redistribution of the CSV broadly is fine for internal dashboard use; check FRED ToS for public redistribution).
- **Sample series seen (2026-08-19)**:
  - `BAMLC0A0CM` last **2026-08-18 = 0.82** (794 rows in default window; tail 08/12→08/18: 0.79→0.82) — *values look low for an IG yield level; treat the series as what FRED labels it and cross-check against ICE if absolute level matters*
  - `BAMLH0A0HYM2` last **2026-08-18 = 2.75** (08/12→08/18: 2.71→2.75)
  - `BAMLEMCBPIOAS` last **2026-08-18 = 1.40**; `BAMLHE00EHYIOAS` last **2026-08-18 = 2.55**
- **Verified**: **Verified live 2026-08-19** — all four series HTTP 200, updated through 2026-08-18. No freeze, no removal, no redirect.
- **Notes & pitfalls**: The YTM-variant IDs some blogs cite (`BAMLC1A0C13YSYTM`, `BAMLH0A0HYM2EYTM`) return **404** — they don't exist on FRED. Effective-yield vs OAS families differ; pick one family per chart. See "Validation of prior claims" for the full verdict.

## FRED — International long-term government yields (IRLTLT01xxx, OECD-sourced) (prior claim 2)

- **What**: Monthly 10Y benchmark government bond yields aggregated by FRED from OECD MEI/MLI: pattern `IRLTLT01{ISO}M156N`.
- **Coverage**: ~20 OECD countries; **China and India are NOT published on FRED**.
- **Frequency & lag**: Monthly, ~6–7 week lag.
- **Access**: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=IRLTLT01DEM156N` etc.
- **Sample series seen**:
  - `IRLTLT01DEM156N` (Germany) last **2026-06-01 = 2.97**
  - `IRLTLT01JPM156N` (Japan) last **2026-06-01 = 2.67**
  - `IRLTLT01GBM156N` (UK) last **2026-06-01 = 4.796**
  - `IRLTLT01USM156N` (US) last **2026-06-01 = 4.47**
  - `IRLTLT01CNM156N` (China) → **HTTP 404, does not exist**
  - `IRLTLT01INM156N` (India) → **HTTP 404, does not exist**
- **Verified**: **Verified live 2026-08-19 for DE/JP/GB/US**; **FAILED for CN/IN (404)**.
- **Notes & pitfalls**: Good monthly cross-check but too slow for a crisis dashboard; use national daily sources (Treasury/ECB/MoF/BOE) as primary. Note the FRED versions are *current* while the same OECD MEI series mirrored on DBnomics are stale (end 2024-01) — FRED's feed is fresher.

## ECB — Euro area government yield curves (YC dataflow, SDMX, keyless)

- **What**: ECB daily estimated euro area government bond yield curves: spot (`SV_C_YM`) and forward, nominal/real/zero-coupon, by issuer rating bucket. Maturities `SR_3M, SR_2Y, SR_5Y, SR_10Y, SR_30Y`, ... full grid.
- **Coverage**: Euro area (U2, changing composition) aggregate curve **split by rating bucket**; also per-country curves via other REF_AREA codes.
- **Frequency & lag**: Daily (TARGET business days), T+1.
- **Access**: Keyless SDMX-CSV:
  `https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?lastNObservations=3&format=csvdata`
  → `csv.DictReader`, columns `TIME_PERIOD, OBS_VALUE`. Full-history JSON alternative (used by the Data Portal UI): `https://data.ecb.europa.eu/data-detail-api/YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y` → list of per-period dicts, **newest-first** (`PERIOD_NAME`, `OBS`), ~8,017 obs since 2004.
- **License & cost**: Free, keyless; ECB standard terms/reuse policy.
- **Sample series seen (all last obs 2026-08-18)**:
  - `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y` (AAA-rated issuers) = **3.2886**
  - `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y` = **2.7805**; `SR_3M` = 2.3391; `SR_30Y` = 3.7376
  - `YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_10Y` (all ratings) = **3.7170**
- **Verified**: **Verified live 2026-08-19** — HTTP 200 with 2026-08-18 observations on both SDMX and detail-api.
- **Notes & pitfalls**: **Key semantics correction**: in `CL_INSTRUMENT_FM`, `G_N_A` = "all issuers whose rating is **triple A**" and `G_N_C` = "**all ratings included**" — the prior AI's premise that G_N_A is "the" aggregate curve is wrong; G_N_A is the AAA curve, G_N_C the all-ratings curve. DSD is `ECB_FMD2` (7 dims: FREQ.REF_AREA.CURRENCY.PROVIDER_FM.INSTRUMENT_FM.PROVIDER_FM_ID.DATA_TYPE_FM). SDMX `data/YC/...` accepts the full 7-part key; short/malformed keys give HTML 400s. The ECB SDMX host occasionally read-timeouts — set timeout ≥60 s and retry.

## ECB — Corporate bond yields for euro area (search result: NOT available)

- **What**: Attempted euro-area corporate bond yield curve, e.g. claimed key `FM.B.U2.EUR.4F.KR.BLBC_C.SV_C_YM.SR_10Y` ("BBB corporate").
- **Coverage**: n/a.
- **Frequency & lag**: n/a.
- **Access**: probed `https://data-api.ecb.europa.eu/service/data/{FM,RTD}/B.U2.EUR.4F.KR...` and DBnomics `ECB/FM` full-text search.
- **License & cost**: n/a.
- **Sample series seen**: none — all probes HTTP 400/404 ("No Series was found"); `KR` in `CL_INSTRUMENT_FM` = "Key interest rate", not corporate; DBnomics `ECB/FM` search for "corporate bond" = 0 hits.
- **Verified**: **FAILED 2026-08-19** — no euro-area corporate yield series exists in ECB RTD/FM dataflows under this key family.
- **Notes & pitfalls**: Use FRED ICE BofA EUR OAS (`BAMLEMCBPIOAS`, `BAMLHE00EHYIOAS`, both verified live) for euro corporate credit, or the ECB CSDB/Dealigic-based datasets (registration, restricted). The claimed "BLBC_C BBB corporate" key is fabricated.

## Japan Ministry of Finance — Daily JGB reference yields

- **What**: JGB secondary-market yields, maturities 1–40Y, daily; plus monthly full-history file.
- **Coverage**: Japan sovereign curve, 1974–present (history file).
- **Frequency & lag**: Daily (JST evening); current-month file refreshes same day; `jgbcme_all.csv` history extends to end of previous month.
- **Access**: Keyless CSV (Shift-JIS encoded!):
  - current month: `https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv`
  - full history: `https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv`
  `requests.get(...).content.decode("sjis", errors="replace")` → CSV rows `YYYY/M/D,1Y,2Y,...,40Y`.
- **License & cost**: Free, keyless; MoF site terms (government work, link-back etiquette).
- **Sample series seen**: current-month file last row **2026/8/18**: 1Y=1.431, 2Y=1.691, 10Y=**2.934**, 30Y=4.103; history file 13,270 rows ending 2026/7/31.
- **Verified**: **Verified live 2026-08-19** — HTTP 200 `text/csv` both files, last obs 2026-08-18.
- **Notes & pitfalls**: The path cited in many older docs (`/english/jgbs/reference_data/`) is **404** — files moved under `/english/policy/jgbs/reference/interest_rate/`. Decode as SJIS (a UTF-8 decode corrupts the header). Dates are `YYYY/M/D` without zero padding. Monthly-history lag means stitch current-month + all-history.

## Bank of England — UK government liability (gilt) yield curves

- **What**: OIS short-end curve + fitted nominal/real/inflation gilt curves (GLC): daily spot & instantaneous-forward, maturities 0.5–25Y (spot grid seen 0.5Y steps to ~7.5Y+, extends to 25Y).
- **Coverage**: UK sovereign, 1979/1992–present (daily files carry current month; separate monthly-history zips).
- **Frequency & lag**: Daily, T+1 (obs for Tuesday available Wednesday).
- **Access**: Keyless zip:
  `https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip`
  → `zipfile.ZipFile(io.BytesIO(r.content))` → member `GLC Nominal daily data current month.xlsx` → `openpyxl` sheet `"4. spot curve"` (dates col A from row 5; maturity grid in row 4 `years:`). Monthly history: `glcnominalddata.zip` (same directory path).
- **License & cost**: Free, keyless; BoE terms of use.
- **Sample series seen**: `GLC Nominal daily, spot curve` last row **2026-08-18**: 2Y = **4.288**, 10Y = **5.151** (12 dated rows = current month).
- **Verified**: **Verified live 2026-08-19** — zip HTTP 200 (341 KB), parsed through openpyxl.
- **Notes & pitfalls**: Needs `openpyxl` (pip install; not preinstalled here). File layout: row 2 title, row 3 "Maturity", row 4 `years:` header, data from row 5; a stale `#VALUE!` row sits between header and data — filter rows whose col A is a datetime. Column count varies by sheet (spot vs fwd). The zip contains 4 workbooks (nominal/real/inflation GLC + OIS).

## UK Debt Management Office — Gilt yields (BLOCKED)

- **What**: DMO quoted yields / daily gilt prices.
- **Coverage**: UK gilts.
- **Frequency & lag**: Daily.
- **Access**: `https://www.dmo.gov.uk/data/gilt-prices-and-yields/` (HTML → xlsx links).
- **License & cost**: Free in a browser.
- **Sample series seen**: none — response body is a **ShieldSquare bot-block page** ("your activity ... made us think that you are a bot", incident ID returned), 15 KB, zero data links.
- **Verified**: **FAILED 2026-08-19** — scripted access blocked by bot protection on every dmo.gov.uk data path probed.
- **Notes & pitfalls**: Use BoE GLC curves (above) as the UK curve source; they are the fitted-official curves anyway. If DMO bid/cover data is ever needed, expect a real-browser (Browser Use) session or manual download.

## DBnomics — multi-provider aggregator (OECD, ECB, BOE, BIS mirrors)

- **What**: Single free JSON API (`api.db.nomics.world/v22`) over 93 providers incl. OECD MEI (IRLTCT/IRLTLT01), ECB (MIR, YC via ECB provider), BOE, IMF.
- **Coverage**: Cross-country monthly yields (OECD), plus everything ECB.
- **Frequency & lag**: Mirrors source; OECD MEI mirrors run ~2.5 years behind in practice (see below).
- **Access**: series list: `GET https://api.db.nomics.world/v22/series/{provider}/{dataset}?q=...&limit=N&observations=0`; values: `GET /v22/series?series_ids=OECD/MEI/JPN.IRLTLT01.ST.M&observations=1` → JSON `series.docs[0].period[] / value[]`. NOTE: v22 route is `/datasets/{provider}` (not `/datasets?provider_code=`), and full-text search is `/v22/search?q=...` (the `/v22/series?q=` combination errors 400 "additional properties").
- **License & cost**: Free, keyless; each provider's license applies; DBnomics terms.
- **Sample series seen (2026-08-19)**:
  - `OECD/MEI/JPN.IRLTLT01.ST.M` last **2024-01 = 0.73** — STALE
  - `OECD/MEI/IND.IRLTLT01.ST.M` last **2024-01 = 7.20** — STALE
  - `OECD/MEI/CHN.IRLTLT01.ST.M` last **2023-12 = 2.56** — STALE
  - `ECB/MIR/...` keys resolve and are current (see MIR card)
- **Verified**: **Verified live 2026-08-19** (API works) but the OECD MEI yield mirrors are **STALE (last obs 2023-12/2024-01)** — unusable as a current feed; FRED's IRLTLT01 versions are the current ones.
- **Notes & pitfalls**: Search only indexes dataset names (not per-series); use provider/dataset/q filters. Use DBnomics for bulk history + as JSON convenience layer for ECB, not for OECD timeliness.

## ECB — MIR bank lending rates (euro area real-economy borrowing cost)

- **What**: MIR = euro area bank interest rates on new loans. Verified key: `MIR.M.U2.B.A2A.A.R.0.2240.EUR.N` = rate on new-business loans (non-revolving) to non-financial corporations (2240), euro area banks, all maturities.
- **Coverage**: Euro area (U2) + per-country; NFC, household (consumption/house purchase) loan & deposit rates.
- **Frequency & lag**: Monthly, ~5–6 weeks (June obs available mid-Aug).
- **Access**: Keyless SDMX-CSV: `https://data-api.ecb.europa.eu/service/data/MIR/M.U2.B.A2A.A.R.0.2240.EUR.N?lastNObservations=2&format=csvdata`; or DBnomics `ECB/MIR` with q-filter.
- **License & cost**: Free, keyless.
- **Sample series seen**: `M.U2.B.A2A.A.R.0.2240.EUR.N` last **2026-06 = 4.11** (prev 2026-05 = 4.05).
- **Verified**: **Verified live 2026-08-19** — HTTP 200 with June 2026 value.
- **Notes & pitfalls**: Key syntax changed from the classic `...A2A.AM.R.A.2240...` (now 404): maturity `A`(all) + amount_cat `0` works, `AM` does not. Household house-purchase variants I tried (`A22.A.R.{0,A}.225x/226x`) returned 404 — enumerate via DBnomics `ECB/MIR` q="house purchase" to find live keys before hardcoding. `.B.` data-type in the same key family is business *volume*, not rate (saw 81707 = volumes).

## FRED — Mortgage rates (household borrowing cost, US)

- **What**: `MORTGAGE30US` — 30-Year Fixed Rate Mortgage Average, Freddie Mac PMMS.
- **Coverage**: US, weekly since 1971.
- **Frequency & lag**: Weekly (Thursday), same week.
- **Access**: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US`.
- **License & cost**: Free via FRED; Freddie Mac PMMS attribution.
- **Sample series seen**: last **2026-08-13 = 6.67** (2,890 weekly rows).
- **Verified**: **Verified live 2026-08-19** — HTTP 200, value as above.
- **Notes & pitfalls**: `MORTGAGE15US`, `MORTGAGE5US` same family. Euro-area household analogue = ECB MIR `A22` (house purchase) keys — resolve via DBnomics (see MIR pitfalls).

## ChinaBond / CFETS chinamoney — China government bond (CGB) yield curve

- **What**: ChinaBond daily CGB yield curve (the official mid/yield curve, chinabond.com.cn) and CFETS curve (chinamoney.com.cn).
- **Coverage**: China sovereign + policy bank curves.
- **Frequency & lag**: Daily.
- **Access**: `https://yield.chinabond.com.cn/` (HTTP 200, 74 KB JS shell); known data POST endpoints (`/cbweb-cbrc-web/cbrc/queryGjqx`) → **HTTP 404**; chinamoney `/ags/ms/cm-u-bk-cccur/CNCCcurv(His)` → **404 "Path not found"**.
- **License & cost**: Free to view in browser; data API requires session/JS (registration for some endpoints).
- **Sample series seen**: none via script.
- **Verified**: **FAILED 2026-08-19** — portal pages load but all programmatic data endpoints probed are gone or gated; no login-free machine path found.
- **Notes & pitfalls**: Honest verdict: no open, stable, login-free daily China curve endpoint. Fallbacks ranked: (1) Investing.com CNY 10Y page (scrapeable but ToS-restricted, not open), (2) commercial APIs (TuShare/akshare — akshare wraps chinabond but same fragility), (3) OECD monthly via FRED — **does not exist** (404, see claim 2), (4) yfinance ETF price proxies — prices only, no curve. Treat China daily curve as an open gap: budget for a licensed vendor (Wind/Refinitiv) or a headless-browser scraper with maintenance.

## India — FBIL / CCIL G-sec benchmark yields

- **What**: FBIL 10Y G-sec benchmark yield (daily 5:30pm IST fix); CCIL underlying.
- **Coverage**: India sovereign benchmark.
- **Frequency & lag**: Daily.
- **Access**: `https://www.fbil.org.in/` → HTTP 200 but a 1.5 KB JS shell, no discoverable public JSON; CCIL `ccilindia.com/Research/Statistics/Pages/GSecYield.aspx` → **HTTP 403**; RBI DBIE portal → free but requires registration (not probed anonymously).
- **License & cost**: Free in browser; no anonymous API.
- **Sample series seen**: none via script.
- **Verified**: **FAILED 2026-08-19** (anonymous programmatic access).
- **Notes & pitfalls**: `IRLTLT01INM156N` on FRED does not exist (404); DBnomics OECD mirror ends 2024-01 (stale). Practical options: register for RBI DBIE (free, manual bulk download), or FRED does carry some India series via other IDs — none verified for daily G-sec yields. Treat as a gap requiring registration or a browser-automation fetch of FBIL's site (which renders data client-side).

## Yahoo Finance (yfinance) — price proxies for bond ETFs & indices

- **What**: Daily prices for IG/HY corporate bond ETFs (US + intl listings) and the ^TNX 10Y yield index. **Proxy-only**: ETF price ≠ index yield; use for direction/stress, not levels.
- **Coverage**: `LQD, HYG, IEF, TLT, SHY, VCSH, VCIT, IGHG` (US IG/HY), `^TNX` (US 10Y), plus Japan/UK listings (unreliable, see pitfalls).
- **Frequency & lag**: Daily, same day close.
- **Access**: `pip install yfinance`; `yf.Ticker("LQD").history(period="5d")`.
- **License & cost**: Free library; Yahoo ToS is grey for automated use — acceptable for prototyping, not for a commercial dashboard.
- **Sample series seen (2026-08-19 close)**: `^TNX` 4.66; `LQD` 106.47; `HYG` 79.71; `IEF` 93.26; `TLT` 82.86; `SHY` 82.02; `VCSH` 78.64; `VCIT` 81.33; `IGHG` 77.76.
- **Verified**: **Verified live 2026-08-19** for US tickers. Tokyo-listed bond ETFs (`8306.T` etc.) returned NaN/404 — not dependable.
- **Notes & pitfalls**: For non-US corporates prefer the FRED ICE BofA EUR OAS series (verified) over ETF proxies; for China/India there is no good Yahoo yield proxy (bond ETFs absent/illiquid). Rate-limiting: yfinance breaks intermittently; cache responses.

---

## Validation of prior claims

**Claim 1 — "FRED ICE BofA US Corporate/HY Effective Yield (BAMLC0A0CM, BAMLH0A0HYM2) free on FRED, great crisis indicator"** → **VERDICT: TRUE / VERIFIED LIVE.**
Both fredgraph.csv endpoints return HTTP 200 and are updated through **2026-08-18** (BAMLC0A0CM = 0.82, BAMLH0A0HYM2 = 2.75; continuous daily tail 08/12→08/18 inspected). No freeze, no removal, no licensing wall visible at the data level. Bonus: the EUR corporate OAS siblings `BAMLEMCBPIOAS` (1.40) and `BAMLHE00EHYIOAS` (2.55) are equally current — use them as the euro-area corporate credit gauge since ECB itself has no corporate yield series. Caveats: (a) sibling YTM-variant IDs (`...SYTM`/`...EYTM`) 404 — don't cite them; (b) the absolute level of BAMLC0A0CM (0.82%) looks anomalously low vs the 4–5% Treasury backdrop — sanity-check the level against ICE/FINRA before displaying it as "the" IG yield; the HY series (2.75) also looks compressed. If levels matter, cross-verify with FINRA TRACE statistics before shipping the dashboard tile.

**Claim 2 — "FRED aggregates international government bond yields (OECD-sourced IRLTLT01xxx)"** → **VERDICT: PARTIALLY TRUE.**
`IRLTLT01DEM156N` (Germany), `IRLTLT01JPM156N` (Japan), `IRLTLT01GBM156N` (UK), `IRLTLT01USM156N` (US) all verified live: HTTP 200, last obs **2026-06-01** (monthly, ~6–7 week lag). **`IRLTLT01CNM156N` (China) and `IRLTLT01INM156N` (India) DO NOT EXIST — HTTP 404.** So FRED international coverage stops at OECD members; for China/India use national sources (which are themselves gated — see gaps) or accept monthly OECD mirrors elsewhere. Also: the same OECD MEI series on DBnomics are frozen at 2023-12/2024-01 — do not use DBnomics OECD for current yields.

## Country × curve matrix

| Country | Govt curve source (verified) | Corporate/private yield source (verified) | Frequency |
|---|---|---|---|
| US | US Treasury daily CSV + FRED DGS2/10/30, DGS3MO (2026-08-17/18) | FRED ICE BofA BAMLC0A0CM, BAMLH0A0HYM2 (2026-08-18); FRED MORTGAGE30US (2026-08-13) | Daily (mortgage weekly) |
| Euro area | ECB SDMX YC G_N_A (AAA) & G_N_C (all ratings), SR_3M…SR_30Y (2026-08-18) | FRED BAMLEMCBPIOAS / BAMLHE00EHYIOAS (2026-08-18); ECB MIR NFC lending rate (2026-06, monthly) | Daily (MIR monthly) |
| Germany | FRED IRLTLT01DEM156N (2026-06, monthly) — daily: use ECB YC per-country REF_AREA | — | Monthly (daily via ECB) |
| UK | Bank of England GLC nominal spot zip→xlsx, 0.5–25Y (2026-08-18); DMO blocked | UK corporate IG/HY: no free verified source — FRED EUR OAS not applicable; use ICE via FRED US-family or yfinance proxies | Daily |
| Japan | MoF jgbcme.csv 1–40Y (2026-08-18) + jgbcme_all.csv history (2026-07-31); FRED IRLTLT01JPM156N monthly | JGB ETF proxies on Yahoo fail; no free J-corp yield verified | Daily |
| China | **GAP** — ChinaBond/chinamoney not scriptable; FRED CN series 404; DBnomics OECD stale 2023-12 | **GAP** | — |
| India | **GAP** — FBIL/CCIL gated (403/JS shell); FRED IN series 404; DBnomics OECD stale 2024-01; RBI DBIE = free registration | **GAP** | — |

## Gaps

- **China daily CGB curve**: no login-free programmatic source found (ChinaBond portal JS-gated, endpoints 404; chinamoney 404; FRED 404; OECD mirror stale). Needs licensed vendor, akshare/TuShare with maintenance risk, or headless-browser scraping.
- **India daily G-sec yield**: FBIL renders client-side; CCIL 403; RBI DBIE requires (free) registration; FRED/DBnomics dead ends. Needs DBIE registration or browser automation.
- **UK corporate IG/HY yield level**: no free verified series (FRED carries ICE BofA US + EUR families; no live GBP effective-yield series probed successfully; FINRA TRACE stats page moved/404). ETF proxy only.
- **Euro-area corporate yield *level***: ECB publishes no corporate yield series (KR ≠ corporate — claimed key fabricated); only OAS (spread) via FRED ICE BofA EUR, or spread-to-swap composites.
- **T10Y2M discontinued** (FRED 404) — compute from DGS10−DGS2.
- **OECD/MEI mirrors on DBnomics stale (2024-01)** — always prefer FRED's IRLTLT01 for the same concept.
- **Level sanity-check needed** on BAMLC0A0CM/BAMLH0A0HYM2 absolute values (0.82%/2.75% look low for 2026 backdrop) — cross-check vs ICE/FINRA before display; spreads/deltas are safe.
- **Reliability**: FRED fredgraph occasionally read-timeouts (retry); ECB SDMX needs ≥60 s timeouts; UK DMO blocks all scripted access (ShieldSquare).
