# Sources 01 — Cross-Country Aggregators (BIS, IMF, World Bank, OECD, DBnomics, FRED)

Verification probes for the debt-monitor dashboard. Every endpoint below was probed live with a Python `requests` script on **2026-08-19** (probe scripts kept on the research host under `/home/ubuntu/probes/` and `/home/ubuntu/probe_*.py`). Cadence rule applied: monthly+ preferred, quarterly accepted, annual only as documented fallback. "Latest obs" = last observation date actually seen in the response/file, not the provider's claimed vintage.

Key environment note: `www.imf.org` (datamapper) and `fred.stlouisfed.org` over HTTPS are behind Akamai and blocked/timeout from this host; both have working alternates documented below.

---

## BIS — Total Credit to the Non-Financial Sector (WS_TC, bulk CSV)

- **What**: Credit to government, households & NPISHs, non-financial corporations, and total non-financial sector, from all sectors (core debt, loans + debt securities). Levels (LC, USD) and % of GDP; nominal/market valuation; break-adjusted. The single best cross-country debt-volume dataset.
- **Coverage**: 48 "Borrowers' country" entries incl. **United States, China, India**, euro area, G20, EME/AE aggregates, + 40 individual economies (AR, BR, CL, ID, KR, MX, RU, SA, TR, ZA, …). Borrowing sectors: General government / Households & NPISHs / Non-financial corporations / Non financial sector (total).
- **Frequency & lag**: Quarterly. Latest observation in file: **2025-Q4** (seen 2026-08-19) → effective lag ≈ 5–7 months for the latest quarter (US, CN, IN all present at 2025-Q4).
- **Access**: Bulk zip `https://data.bis.org/static/bulk/WS_TC_csv_col.zip` (674 KB, one wide CSV, 1,133 series rows, periods as columns 1940-Q2…2025-Q4). Python: `requests.get(url)` → `zipfile.ZipFile(io.BytesIO(r.content))` → `csv.DictReader`. NOTE: host must be **data.bis.org** (www.bis.org/statistics/... bulk paths 404). Same file also as `_csv_flat.zip` and SDMX-2.1 zips.
- **License/cost**: Open, free, no key, no registration. Terms: BIS statistics terms of use (permitted with attribution).
- **Sample series** (seen 2026-08-19, all "…from All sectors – % of GDP – adjusted for breaks", last cell 2025-Q4): US General government = **116.4**; China General government = **99.3**; India General government = **83.9**; China Households & NPISHs = 58; India HH = 47.8; China NFC = 142.8; US NFC = 72.2; US total non-financial = 251.2; China total = 300.1.
- **Verified**: ✅ Verified live 2026-08-19 — HTTP 200, zip parsed, 1,134 CSV lines, values above extracted from the file.
- **Notes/pitfalls**: Wide format (period = column), so reshape to long before ingest. Column names duplicated in code+label pairs (`BORROWERS_CTY` / `Borrowers' country`). % of GDP unit type code is `770`. The historical landing `https://www.bis.org/statistics/totcredit/totcredit_csv.zip` is **dead (404)** — the HTML page `totcredit.htm` is now a JS app with no static links. For higher-frequency debt signals, BIS also publishes monthly credit for some economies via the same dataset (FREQ=M rows exist in some BIS files, but WS_TC bulk is quarterly-dominant — verify per country before promising monthly).

## BIS — SDMX REST API (stats.bis.org v1)

- **What**: SDMX 2.1 REST for all BIS statistics: dataflow catalog, datastructures/codelists, and data queries.
- **Coverage**: 32 dataflows listed, debt-relevant: `WS_TC` (Total credit), `WS_CREDIT_GAP`, `WS_DSR` (debt service ratios), `WS_DEBT_SEC2_PUB` (international debt securities), `WS_SPP`/`WS_DPP` (property prices), `WS_GLI` (global liquidity), `WS_LBS_D_PUB`, `WS_CBPOL`, `WS_XRU`.
- **Frequency & lag**: Per-flow (WS_TC quarterly).
- **Access**: `https://stats.bis.org/api/v1/dataflow/all/all/latest`; `…/api/v1/datastructure/BIS/BIS_TOTAL_CREDIT/latest?references=children` (verified: dims `FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.VALUATION.UNIT_TYPE.TC_ADJUST` + TIME_PERIOD; codelist `CL_AREA` = 101 codes; `CL_TC_BORROWERS` = {C,G,H,N,P}; `CL_VALUATION` = {M,N}).
- **License/cost**: Open, keyless.
- **Sample series**: Dataflow listing 200 (32 flows); DSD 200. Data queries `/api/v1/data/WS_TC/<key>` returned **404** for every key pattern tried (v1 key order/units unresolved in this session). v2/v3 endpoints on data.bis.org/stats.bis.org: 404/501.
- **Verified**: ⚠️ Partially verified 2026-08-19 — structure & catalog endpoints live (HTTP 200 + XML); **data query not confirmed working**. Use bulk CSV (card above) for data; treat SDMX data queries as unproven until a working key is derived from the DSD.
- **Notes/pitfalls**: Don't build the pipeline on the SDMX data endpoint without first resolving the exact 7-dim key (UNIT_TYPE uses numeric codes from `CL_BIS_UNIT`, e.g. `770` = % of GDP; ADJUST values {0,1,A,U}).

## IMF — Global Debt Database (GDD) via SDMX 2.1 (api.imf.org)

- **What**: Total debt stocks (% of GDP) by sector: government (S13), households (S14), non-financial corporations (S11), private sector total (PS), plus financial-corporation and mixed-sector variants, debt-securities components (F3T4_*), nominal GDP (B1GQ_V_XDC).
- **Coverage**: **190 countries** incl. USA, China, India. 11 indicators × annual. Time span 1950–**2024**.
- **Frequency & lag**: **Annual only** (FREQUENCY dimension = 'A' single value). Latest year seen: **2024**. → documented fallback for cross-sections/backfill; cannot serve the monthly cadence.
- **Access**: `https://api.imf.org/external/sdmx/2.1/data/GDD/{COUNTRY}.{INDICATOR}.A` (XML default; JSON via `Accept: application/vnd.sdmx.data+json;version=1.0.0`). Full dump: `/data/GDD/all` (~3.5 MB JSON). Dataflow catalog: `/external/sdmx/2.1/dataflow/all/all/latest` (JSON: 222 flows, GDD v2.0.0). Python: `requests` + regex/`lxml` on SDMX-JSON (`dataSets[0].series` keyed by dim-index, values in `structure.dimensions.observation`).
- **License/cost**: Open, keyless, no registration.
- **Sample series** (seen 2026-08-19): `GDD/USA.FL_S13_POGDP_PT.A` → 75 obs, 2024 = **120.78568**; `GDD/CHN.FL_S13_POGDP_PT.A` → 2024 = **88.327128**; `GDD/IND.FL_S13_POGDP_PT.A` → 2024 = **81.285982**; `GDD/USA.FL_S14_POGDP_PT.A` (households) → 2024 = 71.399727; `GDD/USA.FL_S11_POGDP_PT.A` (NFC) → 2024 = 145.220285; `GDD/USA.FL_PS_POGDP_PT.A` (private) → 2024 = 216.620012.
- **Verified**: ✅ Verified live 2026-08-19 (HTTP 200 on catalog, full dump, and country×indicator queries).
- **Notes/pitfalls**: **CHN/IND private-sector cells are largely empty in this API** — `GDD/CHN|IND.FL_S14/FL_S11/FL_PS…` return `<Obs>` elements *without* `OBS_VALUE` (missing), while S13 (government) has values through 2024. For China/India private debt use BIS WS_TC (quarterly, richer). The old "open API" `https://www.imf.org/external/datamapper/api/v1/…` is **blocked from this host (Akamai 403)** — do not hardcode it. Indicator naming: `FL_<sector>_POGDP_PT` = debt liabilities, % of GDP.

## IMF — World Economic Outlook (WEO) + datamapper status

- **What**: General government gross debt `%GDP` (`GGXWDG_NGDP`), among 145 indicators; actuals + forecasts to 2031. Useful for nowcasting gov-debt trajectory and country breadth (207 countries).
- **Coverage**: 207 countries incl. CHN, IND, USA. Annual.
- **Frequency & lag**: Annual; vintage ~Apr + Oct. Latest actual seen: 2024/2025; forecasts through **2031**. Dataset carries `WEO_2025_OCT_VINTAGE` in the new API catalog → October 2025 vintage live.
- **Access**: `https://api.imf.org/external/sdmx/2.1/data/WEO/USA+CHN+IND.GGXWDG_NGDP.A` (same SDMX 2.1 host as GDD). JSON dump `/data/WEO/all` ≈ 3.5 MB, 8,041 series keys.
- **License/cost**: Open, keyless.
- **Sample series** (seen 2026-08-19, series order CHN/IND/USA): CHN `GGXWDG_NGDP` 2030 = 123.789 (fcst); IND 2030 = 79.465; USA 2030 = 138.897, 2031 = 142.113.
- **Verified**: ✅ Verified live 2026-08-19 (HTTP 200, obs parsed).
- **Notes/pitfalls**: WEO is **forecasts+actuals** — filter `TIME_PERIOD <= current year` for actuals. Datamapper (`/external/datamapper/api/v1/`) is 403-blocked here (Akamai); the api.imf.org SDMX route is the working replacement. IFS: the 222-flow catalog on api.imf.org shows monetary/financial flows under `MFS_*` (MFS_CBS, MFS_DC, MFS_ODC, …) — no flow literally named "IFS"; the legacy IFS remains accessible via the **DBnomics IMF/IFS mirror** (below).

## World Bank — Bank NPL ratio (FB.AST.NPER.ZS)

- **What**: Bank nonperforming loans to total gross loans (%). Health indicator for the banking system, all economies.
- **Coverage**: ~217 economies + aggregates (1,590 rows for 2019–2024 window).
- **Frequency & lag**: **ANNUAL** (confirmed: `date` values are years only). Latest year seen: **2025** for USA (0.9603%) and IND (2.0628%); CHN latest = **2024** (1.5046%). DB lastupdated tag: 2026-07-13.
- **Access**: `https://api.worldbank.org/v2/country/all/indicator/FB.AST.NPER.ZS?format=json&per_page=…&date=2019:2024` (verified 200). Multi-country: `/country/US;CN;IN/indicator/…`.
- **License/cost**: Open, keyless.
- **Sample series**: `FB.AST.NPER.ZS` USA 2025 = 0.960307; IND 2025 = 2.062836; CHN 2024 = 1.504552 (seen 2026-08-19).
- **Verified**: ✅ Verified live 2026-08-19.
- **Notes/pitfalls**: Annual → **fails the monthly preference and is only a fallback** for health metrics. For monthly banking stress use national sources (another researcher's domain). Pagination: 1,590 total rows / `per_page` must be set high or paged.

## World Bank — WDI nominal GDP + CPI (support series)

- **What**: `NY.GDP.MKTP.CD` (nominal GDP, current US$) and `FP.CPI.TOTL` (CPI index 2010=100) for deflating/converting debt stocks.
- **Coverage**: All WDI countries (US/CN/IN/DE confirmed).
- **Frequency & lag**: Annual. Latest seen: GDP USA **2025** = 30,769.7bn; CPI USA **2024** = 143.857; CHN 2024 = 132.5; IND 2024 = 227.6; DEU 2024 = 134.9.
- **Access**: `https://api.worldbank.org/v2/country/{ISO3}/indicator/{code}?format=json&per_page=80` (verified 200).
- **License/cost**: Open CC-BY-4.0, keyless.
- **Sample series**: above (seen 2026-08-19).
- **Verified**: ✅ Verified live 2026-08-19.
- **Notes/pitfalls**: Annual only — fine as denominators for annual ratios; BIS WS_TC already ships % of GDP so WDI is cross-check. (GDP/CPI depth owned by another researcher.)

## FRED — as international aggregator (keyless fredgraph.csv)

- **What**: St. Louis Fed mirrors OECD- and BIS-sourced international series (OECD MEI CPI/rates, discontinued BIS central-gov-debt "DDDI…" series) alongside US domestic series.
- **Coverage**: Global via OECD/BIS sourced IDs; but series-by-series survival varies.
- **Frequency & lag**: Source-dependent (monthly for MEI rates/CPI, annual for DDDI).
- **Access**: Keyless CSV: `http://fred.stlouisfed.org/graph/fredgraph.csv?id={SERIES}` — **plain HTTP with a curl User-Agent works from this host; HTTPS read-times out (Akamai edge)**. Official JSON API (`api.stlouisfed.org/fred/…`) requires a **free API key** (probe without key: HTTP 400 "Variable api_key is not set").
- **License/cost**: fredgraph.csv free/keyless; official API free registration.
- **Sample series** (seen 2026-08-19):
  - `IR3TIB01USM156N` (OECD, 3M T-bill, monthly): 746 rows, **last 2026-06-01 = 3.77 → still updating** ✅
  - `CPALTT01USM657N` (OECD MEI, CPI growth, monthly): 831 rows, **last 2024-03-01 → frozen** ❌ (OECD MEI discontinued)
  - `HSTDGCAFAOMXMEI` (OECD house price-to-income): **404 — discontinued** ❌
  - `DDDI05USA156NWDB` (central gov debt, %GDP, annual): 62 rows, **last 2020-01-01 = 91.689 → frozen 6 years** ❌
  - Control `BAMLH0A0HYM2` (ICE BofA US HY OAS, daily): last **2026-08-18** = 2.75 → method itself is sound; endpoint live ✅
  - Guessed BIS-sourced IDs (`HOLGBBQ188M/Q`, `Q2TCGBGG5A`, …): all 404 — no live BIS credit-to-GDP mirror found on FRED.
- **Verified**: ✅ Endpoint verified live 2026-08-19 (mixed content verdict).
- **Notes/pitfalls**: **Verdict: FRED is NOT a dependable primary source for international debt aggregates** — the OECD-MEI-sourced family froze in 2024-03 or 404'd, and BIS-sourced debt IDs are gone; only scattered survivors (e.g. `IR3TIB01*`) still update. Use BIS/IMF/OECD directly; use FRED only for US-domestic and market-credit-spread series. Prefer HTTP+curl-UA or get the free API key.

## DBnomics — multi-provider meta-aggregator

- **What**: Keyless JSON API aggregating 93 providers: **BIS, IMF, OECD, ECB, WB, Eurostat, BEA**, national statistical offices — one uniform `/v22` interface over all of them.
- **Coverage**: 93 providers verified. Debt-relevant mirrors confirmed: `BIS/WS_TC` ("BIS long series on total credit", 1,133 series), `IMF/IFS` (193,984 series), `IMF/HPDD` (historical public debt), `IMF/WEO:*` vintages (latest mirrored: **WEO:2025-04**), `OECD/*` (1,403 datasets incl. DP_LIVE), `ECB` (indexed 2026-07-25).
- **Frequency & lag**: Mirror lag matters: BIS `WS_TC` mirror `indexed_at` = **2025-06-20** → its latest obs is 2024-Q4 vs **2025-Q4** in the BIS bulk file (≈ 3 quarters behind).
- **Access**: `https://api.db.nomics.world/v22/providers`; series: `/v22/series/{PROVIDER}/{DATASET}/{SERIES_CODE}?observations=1`; search `/v22/search?q=…`; dataset listing `/v22/datasets/{PROVIDER}`. Python: `requests` + dict access (`series.docs[0].period / .value`).
- **License/cost**: Free, keyless, no visible rate-limit headers (fair-use; no documented hard limit encountered).
- **Sample series** (seen 2026-08-19): `BIS/WS_TC/Q.US.G.A.M.770.A` (US gov credit, %GDP, market value): 309 obs, last **2024-Q4 = 106.3**. `OECD/DP_LIVE/AGO.OILPROD.TOT.KTOE.A`: last 2021. `IMF/IFS` US monthly monetary series listed (obs not fetched).
- **Verified**: ✅ Verified live 2026-08-19 (providers, dataset listings, series with observations).
- **Notes/pitfalls**: `/v22/datasets/BIS` (whole-provider listing) returns **404 with "Could not load dataset.json for dataset BIS/cbpol"** — a broken dataset record breaks the listing; work around by querying known dataset codes or `/v22/series/BIS/{code}` directly. Search (`/v22/search`) returned 0 hits for exact series codes — don't rely on it. Mirror lag + occasional broken datasets → prefer upstream for production, DBnomics for prototyping/cross-checks.

## OECD — SDMX 3.0 (sdmx.oecd.org) + DBnomics mirror

- **What**: OECD's own SDMX endpoint for 1,545 dataflows. Debt-specific flows are narrow (household-debt microdata: `DSD_DEBT_TRANS_COLL@DF_MICRO`, `DSD_DEBT_TRANS_DDOWN@DF_DDOWN`, `DSD_DASHBOARD@DEBT`); the broad MEI family that used to feed FRED is discontinued.
- **Coverage**: OECD members + partners.
- **Frequency & lag**: Varies; the mirrored `OECD/MEI` CPI series ends 2023-12 (frozen). No broad cross-country government/private debt stock dataset found — **OECD is not a primary debt-volume aggregator for this project** (use BIS/IMF; Eurostat for EU detail).
- **Access**: `https://sdmx.oecd.org/public/rest/dataflow/all/all/latest` with header `Accept: application/xml` (8.9 MB, works). JSON accept → **HTTP 406**. Data: `…/public/rest/data/{flow-ref}/{key}?format=jsondata`. Simpler: DBnomics `OECD/*` mirror.
- **License/cost**: Open, keyless.
- **Sample series**: `OECD/MEI/USA.CPALTT01.GY.M` via DBnomics: 816 obs, last **2023-12 = 3.35** (seen 2026-08-19).
- **Verified**: ✅ Flow catalog + mirrored series verified live 2026-08-19.
- **Notes/pitfalls**: Send XML accept or use `format=jsondata` per-query; the 406 on JSON structure queries is a trap. Household-debt dashboard data is annual.

---

## Validation of prior claims

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | BIS totcredit: "CSV/REST API, 40+ economies, gov+HH+corp" | **Mostly TRUE, endpoint WRONG.** 48 borrower countries incl. China + India; sectors G/H/NFC/total; quarterly; bulk CSV works — but at `https://data.bis.org/static/bulk/WS_TC_csv_col.zip`, **not** the claimed `www.bis.org/statistics/totcredit/totcredit_csv.zip` (404). SDMX REST: structure/catalog live, data queries unresolved (404s on all key patterns tried). Latest obs **2025-Q4**. | HTTP 200 + zip parsed; 404s logged |
| 2 | IMF GDD: "190 countries, public+private, open API" | **TRUE on new API, FALSE endpoint.** 190 countries, annual, 1950–**2024**, private components exist (HH `FL_S14`, NFC `FL_S11`, private total `FL_PS`) — but **CHN/IND private cells are NA** in this API; the claimed `datamapper/api/v1` is 403-blocked. Working endpoint: `https://api.imf.org/external/sdmx/2.1/data/GDD/…`. | USA S13 2024=120.786; CHN=88.327; IND=81.286 |
| 3 | WB `FB.AST.NPER.ZS` annual, fails monthly rule | **CONFIRMED.** Annual only; latest year 2025 (USA/IND) / 2024 (CHN). Use as documented fallback health metric. | HTTP 200; USA 2025=0.960 |
| 4 | FRED "aggregates OECD and BIS international debt statistics" | **MIXED → effectively FALSE for debt.** OECD-MEI-sourced series frozen at 2024-03 or 404; BIS-sourced debt IDs not found live; only scattered OECD survivors update (IR3TIB01 → 2026-06). Do not use FRED as the international debt pipe. | fredgraph.csv probes above |
| 5 | DBnomics keyless, mirrors BIS/IMF/OECD/ECB/national | **TRUE.** 93 providers, keyless, all four + Eurostat/BEA/WB confirmed; pitfalls: broken `BIS` dataset listing (404) and ~3-quarter mirror lag on BIS WS_TC (2024-Q4 vs upstream 2025-Q4). | providers list + WS_TC obs |
| 6 | IMF IFS + WEO via API | **WEO: TRUE** (api.imf.org SDMX 2.1, 207 countries, GGXWDG_NGDP verified, Oct-2025 vintage). **IFS: PARTIAL** — no flow named "IFS" on api.imf.org (monetary data under MFS_*); legacy IFS reachable via DBnomics `IMF/IFS` (193,984 series, listing verified; obs not fetched). | probes B/E/H |

## Coverage snapshot

| Aggregator | Countries | Best frequency | Domains | Freshness seen (2026-08-19) |
|---|---|---|---|---|
| BIS WS_TC (bulk) | 48 (US, CN, IN ✓) | Quarterly | Gov + HH + NFC credit volumes & %GDP | 2025-Q4 |
| IMF GDD (SDMX 2.1) | 190 (US, CN, IN ✓; CN/IN private NA) | Annual | Gov + HH + NFC + private debt %GDP | 2024 |
| IMF WEO (SDMX 2.1) | 207 | Annual | Gov gross debt %GDP (actual+fcst) | 2025 actual / 2031 fcst |
| World Bank NPL | ~217 | Annual | Bank health (NPL %) | 2025 (US/IN), 2024 (CN) |
| World Bank WDI | ~217 | Annual | GDP, CPI (denominators) | 2025 GDP / 2024 CPI |
| DBnomics (BIS/IMF/OECD/ECB mirror) | 93 providers | Inherited (Q/A) | All of the above (lagged) | BIS TC mirror 2024-Q4 |
| FRED (OECD/BIS mirrors) | partial | Monthly (survivors) | Rates/CPI; debt mirrors dead | 2026-06 (rates) / frozen |
| OECD SDMX | OECD+ | Annual (debt flows) | Household-debt microdata only | MEI mirror 2023-12 |

**Recommended stack for the dashboard**: BIS WS_TC bulk CSV (quarterly volumes, the workhorse) + IMF GDD/WEO via api.imf.org SDMX 2.1 (annual breadth & government debt) + WB NPL (annual banking-health fallback) + DBnomics for prototyping; skip FRED/OECD for international debt.
