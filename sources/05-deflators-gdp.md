# Sources 05 — Deflators & Nominal GDP (CPI/HICP monthly + quarterly nominal GDP)

Verification probes for the debt-monitor dashboard, deflator/GDP block. Endpoints probed live with single-file Python `requests` scripts on **2026-08-19** (probe scripts on the research host: `~/probes/p05a…p05e*.py`). Cadence rule: monthly+ preferred, quarterly accepted, annual only as documented fallback. "Latest obs" = last observation date actually seen.

Purpose in the pipeline: (a) deflate nominal debt stocks over time (CPI/HICP), (b) normalize debt by nominal GDP. Note BIS Total Credit already ships a `% of GDP` variant (unit code `770`) — the sources below are for independent normalization, cross-checks, and non-BIS countries.

Environment notes (confirmed this session): `fred.stlouisfed.org` HTTPS times out from this host → **plain HTTP + curl User-Agent** works. Eurostat dissemination API is keyless. ECB data API keyless (`data-api.ecb.europa.eu`). IMF SDMX works at `api.imf.org` but the practical route for IFS is the **DBnomics `IMF/IFS` mirror**. China `data.stats.gov.cn` → HTTP 403 (blocked).

---

## Eurostat — HICP monthly: prc_hicp_minr (new ECOICOP classification) + frozen predecessors

- **What**: Harmonised CPI monthly: annual rates of change (`RCH_A`), monthly rates (`RCH_M`), 12-month moving average (`RCH_MV12MAVR`), index levels 2015=100 (`I15`) and 2025=100 (`I25`), by classification item.
- **⚠️ Classification break at 2026-01 (verified live)**: HICP moved to the new ECOICOP v2 classification from **January 2026**. The new dataset is **`prc_hicp_minr`** (item dimension **`coicop18`**, all-items code **`TOTAL`**) — it carries **full back-history 1997-01 → 2026-07** on the new classification, so no splicing is needed. The predecessor datasets (`prc_hicp_manr`, `prc_hicp_aind`, COICOP codes like `CP00`) are **frozen at 2025-12** (verified: `manr` EA20 CP00 last = 2025-12 = 2.0; `sinceTimePeriod=2026-01` returns empty) — keep them only for pre-2026 cross-checks.
- **Coverage**: 46 geos incl. `EA` (**euro area changing composition** — EA becomes 21 members in 2026), `EA21` (2026 fixed), `EA20` (2023–2025), `EA19`, `EU`, `EU27_2020` + all member states. 555 item codes. Use `EA` for a continuous series; do NOT silently splice `EA20`→`EA21` (composition break).
- **Frequency & lag**: Monthly; latest obs seen **2026-07** (EA annual rate 2.9, monthly rate 0.2, index I25 103.24) ≈ 3-week lag. Current and healthy.
- **Access (exact)**: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr?format=JSON&lang=EN&freq=M&coicop18=TOTAL&geo=EA&unit=RCH_A` → JSON-stat 2.0. Values keyed by flattened multi-dimension position (parse `dimension.time.category.index` to map — naive tail reads return false `None`s). Same call with `unit=I25`/`I15` for levels, `unit=RCH_M` for monthly rates.
- **License/cost**: Open, keyless (Eurostat reuse policy).
- **Sample series seen (2026-08-19)**: `minr` EA TOTAL `RCH_A`: 2026-03=2.6, 04=3.0, 05=3.2, 06=2.8, **07=2.9**; EA `I25` 2026-07=103.24; EA21 07=3.0; EA20 07=2.9; EU27 07=3.0; DE 07=2.8 (I25 103.2); FR 07=2.4. Full-history pull: 355 obs from 1997-01.
- **Verified**: ✅ Verified live 2026-08-19 (structure + 2026 values + history depth; predecessors' freeze confirmed).
- **Notes/pitfalls**: Dimension is **`coicop18`** (not `coicop`) — a `coicop=` filter returns HTTP 400 "dimension COICOP is not defined". All-items = **`TOTAL`** (not `CP00`). Eurostat occasionally returns HTTP 413 "asynchronous response" on very wide queries — filter by geo+unit and retry. HICP rates are essentially not revised post-publication — good for a monitoring pipeline. Index-base choice: `I25` (2025=100) is the new base; `I15` also served in `minr`.

## ECB — ICP (HICP via SDMX, euro area U2 changing composition)

- **What**: The ESCB's HICP mirror in SDMX: annual rates of change (`ANR`), index (`INX`), by COICOP item.
- **Coverage**: Euro area aggregate `U2` (**changing composition** — matches the project requirement; U2 becomes EA21-weighted as of 2026) + all national `REF_AREA`s (DE, FR, IT, ES verified).
- **Frequency & lag**: Monthly. Latest obs seen: **2025-12** — frozen alongside the ECOICOP v1 datasets; with ECOICOP v2 live at Eurostat (`prc_hicp_minr`, above), ECB ICP will presumably follow with a v2 key family — re-probe before relying on it for 2026 data.
- **Access (exact)**: `https://data-api.ecb.europa.eu/service/data/ICP/M.U2.N.000000.4.ANR?format=csvdata&lastNObservations=3` → SDMX-CSV (`TIME_PERIOD, OBS_VALUE`). DSD dims: `FREQ.REF_AREA.ADJUSTMENT.ICP_ITEM.STS_INSTITUTION.ICP_SUFFIX`.
- **License/cost**: Free, keyless (ECB reuse terms).
- **Sample series seen (2026-08-19)**:
  - `M.U2.N.000000.4.ANR` (EA, annual rate): 2025-10 = 2.1, 2025-11 = 2.1, **2025-12 = 1.9**
  - `M.U2.N.000000.4.INX` (EA index level): 2025-11 = 129.33, **2025-12 = 129.54**
  - `M.DE.N.000000.4.ANR`: **2025-12 = 2.0**; `M.FR…`: 0.7; `M.IT…`: 1.2; `M.ES…`: 3.0
- **Verified**: ✅ Verified live 2026-08-19 (U2 + DE/FR/IT/ES).
- **Notes/pitfalls**: **`ICP_ITEM` is 6-digit (`000000` = overall index)** — the 4-digit `0000` form used by older docs returns 404. `U2 ≠ EA20`: U2 changed composition when the euro area expanded to 21 (2026), EA20 is fixed — the 2025-12 gap between U2 (1.9) and Eurostat EA20 (2.3) reflects composition, not error. Monthly-rate suffix `MOR` → 404 (only ANR/INX verified). Structure queries need XML Accept (JSON → 406).

## FRED — US CPI + nominal GDP (fresh US block)

- **What**: `CPIAUCSL` (CPI-U, NSA, monthly) and `GDP` (nominal GDP, quarterly, current $, SAAR) — the US deflator/normalization pair.
- **Coverage**: US.
- **Frequency & lag**: CPI monthly (~2 weeks); GDP quarterly (~4 weeks). Both fresh.
- **Access (exact)**: `http://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL` — **plain HTTP + `User-Agent: curl/8.5.0`** (HTTPS times out from this host). Two-column CSV `observation_date,value`.
- **License/cost**: Free, keyless (FRED terms).
- **Sample series seen (2026-08-19)**: `CPIAUCSL` last **2026-07-01 = 332.813** (955 obs); `GDP` last **2026-04-01 = 32,475.210** $bn (318 obs, i.e. 2026-Q2 advanced).
- **Verified**: ✅ Verified live 2026-08-19.
- **Notes/pitfalls**: Values are levels (index 1982-84=100) — compute your own YoY. For monthly US GDP there is no free official series (S&P/Moody monthly GDP are licensed) — interpolate quarterly or skip.

## FRED — international CPI (OECD-MEI sourced): STALE — do not use

- **What**: `GBRCPIALLMINMEI`, `JPNCPIALLMINMEI`, `INDCPIALLMINMEI`, `CPALTT01GBM659N`, `CPALTT01INM657N`, `CPALTT01USM657N` (OECD-sourced CPI levels/growth).
- **Verdict (2026-08-19)**: ❌ **All stale or dead**: GBR index last **2025-03**, IN index last **2025-03**, JPN index last **2021-06** (frozen 5 years), `CPALTT01USM657N` last **2024-03**, `CPALTT01INM657N` last **2024-01**. Same OECD-MEI discontinuation pattern found in the aggregator dossier (file 01). Use IFS/Eurostat/ECB instead.
- **Verified**: ✅ Probed live 2026-08-19 (HTTP 200s with stale tails; the freshness is the failure).

## IMF IFS (via DBnomics mirror) — monthly CPI + quarterly nominal GDP for non-EU countries

- **What**: IFS `PCPI_IX` (CPI, all items, index) monthly; `NGDP_SA_XDC` / `NGDP_XDC` (nominal GDP, domestic currency) quarterly/annual. The practical keyless route for **UK, Japan, China, India** (+ US/EU cross-check).
- **Coverage**: ~190 countries; verified GB/JP/CN/IN/US monthly CPI and GB/US/DE/FR/IT/IN quarterly GDP.
- **Frequency & lag**: CPI monthly; GDP quarterly (annual for CN). **Mirror lag ≈ 12–13 months**: CPI tails seen 2025-06/2025-07; GDP tails 2025-Q1/2025-Q2. Acceptable for deflators (deflators need long stable histories more than same-week freshness), but document the lag.
- **Access (exact)**: `https://api.db.nomics.world/v22/series/IMF/IFS/M.CN.PCPI_IX?observations=1&format=json` → `series.docs[0].period[] / value[]`. Dataset-scoped search `/v22/series/IMF/IFS?q=consumer+price+index` works (global `q` on `/v22/series` is rejected).
- **License/cost**: Free, keyless (IMF © terms via DBnomics).
- **Sample series seen (2026-08-19)**:
  - CPI index: `M.GB.PCPI_IX` 2025-07 = 153.69; `M.JP.PCPI_IX` 2025-06 = 117.81; **`M.CN.PCPI_IX` 2025-07 = 132.57**; `M.IN.PCPI_IX` 2025-06 = 231.56; `M.US.PCPI_IX` 2025-07 = 148.15
  - Nominal GDP quarterly (SA): `Q.GB.NGDP_SA_XDC` 2025-Q1 = 738,159 (£mn); `Q.JP` 2025-Q1 = 156,330,300 (¥100mn? unit per IFS); `Q.IN` 2025-Q1 = 85,834,792.3 (₹10mn?); `Q.US` 2025-Q2 = 7,582,779 ($mn); `Q.DE` 2025-Q2 = 1,113,285 (€mn); `Q.FR` 2025-Q2 = 743,634; `Q.IT` 2025-Q1 = 554,823
  - **China quarterly GDP: 404 in IFS** — annual only: `A.CN.NGDP_XDC` **2024 = 134,908,360** (¥100mn ≈ ¥134.9tn)
- **Verified**: ✅ Verified live 2026-08-19 (12+ series with observations).
- **Notes/pitfalls**: DBnomics mirror lag (~13 months) vs upstream — for fresher quarters probe the newer `api.imf.org` SDMX (IFS-style flows live under `MFS_*` there; not yet mapped). China has NO quarterly nominal GDP in IFS — use annual, or NBS directly (blocked), or DBnomics `NBS` provider (untested this session). Check IFS `unit_mult` metadata before publishing absolute levels (₹/¥ scale factors differ).

## Eurostat — quarterly nominal GDP (namq_10_gdp): UNRESOLVED combo

- **What**: ESA 2010 quarterly national accounts — nominal GDP (`B1GQ`) current prices for EA/EU aggregates + members.
- **Probe result (2026-08-19)**: dataset + dimensions resolve (HTTP 200) but the probed filter combos — `geo=EA20&na_item=B1GQ` × `unit∈{CP_MNAC, CP_MEUR}` × `s_adj∈{NSC, SCA, CA}` since 2025-Q1 — returned **all-null values** (6 time slots, `value` empty). The correct unit/s_adj/na_item combo for the aggregate was not pinned this session (likely needs `CP_MNAC` + `NSC` at full coverage or a different na_item like `B1GQ_C`; or values sit under a different geo key).
- **Verified**: ⚠️ Structure verified; values NOT obtained. Treat as pending — one more probe session with the Eurostat table browser open should pin it. **Interim euro-area/EA-member quarterly nominal GDP**: IMF IFS `Q.DE/Q.FR/Q.IT…` (2025-Q2, 13-month lag) or ECB MNA dataflow via the ECB Data Portal UI (SDMX keys for the aggregate returned 400 this session; portal itself serves it — `Q.I9…` family per file 03's QSA note).

## World Bank WDI — annual GDP/CPI fallback (cross-check)

- **What**: `NY.GDP.MKTP.CD` (nominal GDP, current US$), `FP.CPI.TOTL` (CPI index 2010=100).
- **Frequency & lag**: Annual. Latest seen: GDP **2025** (USA = $30.77tn); CPI **2024** (USA 143.857, CHN 132.5, IND 227.6, DEU 134.9).
- **Access**: `https://api.worldbank.org/v2/country/{ISO3}/indicator/NY.GDP.MKTP.CD?format=json&per_page=80` (verified 200, file 01 probes).
- **Verified**: ✅ Verified live 2026-08-19 (by the aggregator stream).
- **Notes/pitfalls**: Annual-only fallback; USD conversion uses period-average FX — fine for cross-country levels, not for deflation.

## China NBS — direct: BLOCKED

- `https://data.stats.gov.cn/english/easyquery.htm` → **HTTP 403** (2026-08-19). No keyless route; IFS mirror (above) is the working path for CN CPI (monthly, 2025-07 seen) + annual GDP. Quarterly CN GDP: consider DBnomics `NBS` provider (untested) or accept annual.

## UK ONS — CPI/GDP: API DECOMMISSIONED

- The ONS timeseries API (`api.ons.gov.uk`) is **retired** (confirmed by the government-debt stream, file 02: response body announces decommissioning). UK CPI/GDP working routes: **IMF IFS mirror** (`M.GB.PCPI_IX` 2025-07; `Q.GB.NGDP_SA_XDC` 2025-Q1) + FRED `GBRCPIALLMINMEI` (stale at 2025-03, cross-check only) + ONS website manual download. Re-probe the new ONS platform (beta) before production.

---

## Country × source matrix (verified 2026-08-19)

| Country | CPI/HICP source (freq, latest seen) | Nominal GDP source (freq, latest seen) |
|---|---|---|
| US | FRED `CPIAUCSL` (M, **2026-07**) | FRED `GDP` (Q, **2026-Q2**) |
| Euro area | **Eurostat `prc_hicp_minr`** EA TOTAL RCH_A/I25 (M, **2026-07**) — new ECOICOP v2; ECB ICP U2 (M, 2025-12, frozen) | IFS `Q.DE/FR/IT` members (Q, 2025-Q2); Eurostat namq pending; ECB MNA via portal |
| Germany / FR / IT / ES | **Eurostat `minr` national** (M, **2026-07**; DE 2.8, FR 2.4 verified); ECB ICP national frozen 2025-12 | IFS quarterly (Q, 2025-Q1/Q2) |
| UK | IFS `M.GB.PCPI_IX` (M, 2025-07); FRED stale 2025-03 | IFS `Q.GB.NGDP_SA_XDC` (Q, 2025-Q1) |
| Japan | IFS `M.JP.PCPI_IX` (M, 2025-06); FRED JPN dead 2021 | IFS `Q.JP.NGDP_SA_XDC` (Q, 2025-Q1) |
| China | IFS `M.CN.PCPI_IX` (M, 2025-07); NBS 403 | IFS annual only (`A.CN.NGDP_XDC` 2024) — quarterly gap |
| India | IFS `M.IN.PCPI_IX` (M, 2025-06) | IFS `Q.IN.NGDP_SA_XDC` (Q, 2025-Q1) |
| ~190 others | IFS PCPI_IX monthly (mirror lag) | IFS quarterly where reported; WDI annual |

## Gaps

1. **HICP 2026 classification break — resolved**: `prc_hicp_manr`/`aind` (ECOICOP v1) are frozen at 2025-12 by design; the successor **`prc_hicp_minr`** (ECOICOP v2, dim `coicop18`, all-items `TOTAL`) serves 1997-01→2026-07 continuously. ECB ICP still ends 2025-12 — re-probe for an ECB v2 key family before using it for 2026.
ag.
2. **Eurostat namq_10_gdp values unpinned** (nulls under probed combos) — needs one browser-assisted session; interim = IFS quarterly members.
3. **China quarterly nominal GDP** — IFS 404, NBS blocked; candidates: DBnomics `NBS` provider, or annual-only fallback.
4. **UK after ONS API decommission** — IFS mirror is 13 months lagged; new ONS platform probe pending; manual download fallback.
5. **IFS mirror lag (~13 months) via DBnomics** — for fresher national CPI/GDP probe `api.imf.org` MFS flows or national SDMX (destatis/ISTAT/etc.) per country.
6. **Unit multipliers** (¥/₹ scale) unverified in IFS mirror metadata — confirm before displaying absolute GDP levels.
