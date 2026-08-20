# Debt Monitor — Source Dossier 03: Private Debt Stocks (Households & Non-Financial Corporations)

Debt **stock** (amounts outstanding) series for households (mortgages, consumer credit, total) and non-financial corporations (loans, debt securities, total), plus the private-non-financial aggregate. Level series preferred (%GDP as cross-check). Companion dossiers: 01 (aggregators), 06 (yields); delinquency/flows are covered elsewhere.

All endpoints below were probed live with single-file Python `requests` scripts (fetch + parse in one process, no shell pipes) on **2026-08-19**. "Last obs" = the latest observation actually seen in a response body, not a provider's claimed vintage. Cadence rule: monthly+ preferred, quarterly accepted, annual = documented fallback only.

Environment notes that shape access choices (verified 2026-08-19):
- `fred.stlouisfed.org` over **HTTPS times out** from this host (Akamai edge). Workaround: `http://fred.stlouisfed.org/graph/fredgraph.csv?id=…` with a curl User-Agent, or — preferred for Fed data — the keyless **DBnomics mirror** (`FED/Z1`, `FED/H8`).
- Direct US Federal Reserve DDP endpoints (`www.federalreserve.gov/datadownload/…`) return **HTTP 400** (DDP retired → FRED). DBnomics is the working keyless Fed route.
- ECB SDMX (`data-api.ecb.europa.eu`) is fully keyless — no FRED/DBnomics detour needed.

---

## BIS — Total Credit to the Non-Financial Sector (WS_TC bulk CSV) — the workhorse

- **What**: Amounts outstanding of credit (loans + debt securities, "core debt") to households & NPISHs, non-financial corporations, and the combined private non-financial sector, from all sectors. Also general government (owned by dossier 01). Units: local currency (XDC), USD, % of GDP (`770`), and a ratio unit (`799`) used only for BIS aggregate areas. Break-adjusted (`TC_ADJUST=A`) and unadjusted (`U`) variants; market (`M`) and nominal (`N`) valuation.
- **Coverage**: 48 BORROWERS_CTY entries have both HH and NFC series — 43 individual countries (US, CN, IN, JP, GB, DE, FR, …) + 5 aggregates (XM euro area, G2, 4T, 5A, 5R). Borrowing-sector codes: `H` households & NPISHs, `N` NFCs, `P` private non-financial sector, `G` government, `C` total non-financial.
- **Frequency & lag**: Quarterly (FREQ=Q is the only frequency in the bulk file). Latest observation seen: **2025-Q4** for US, CN, IN, XM, GB, JP (probed 2026-08-19) → effective lag ≈ 5–7 months.
- **Access**: Bulk zip `https://data.bis.org/static/bulk/WS_TC_csv_col.zip` — keyless. Python: `requests.get(url)` → `zipfile.ZipFile(io.BytesIO(r.content))` → `csv.DictReader`. One wide CSV, 1,133 series rows, periods as columns (1940-Q2 … 2025-Q4). Series key format: `Q:{CTY}:{BORROWERS}:{LENDERS=A}:{VALUATION=M|N}:{UNIT}:{ADJUST}`. Host **must** be `data.bis.org` — the legacy `www.bis.org/statistics/totcredit/totcredit_csv.zip` is **404**. Flat (`_csv_flat.zip`) and SDMX-2.1 zips also exist at the same path.
- **License & cost**: Free, keyless, no registration; BIS statistics terms of use (attribution).
- **Sample series** (seen 2026-08-19, all 2025-Q4):
  - `Q:US:H:A:M:USD:A` — US households, USD bn → **20,934.5**
  - `Q:US:N:A:M:USD:A` — US NFCs, USD bn → **22,209.3**; `Q:US:P:A:M:770:A` private sector %GDP → **140.3**
  - `Q:XM:H:A:M:USD:A` — euro area HH, USD bn → **9,389.1**
  - `Q:CN:H:A:M:XDC:A` — China HH, CNY bn → **81,257.7** (≈ CNY 81.3tn); `Q:CN:N:A:M:XDC:A` → 200,093.9
  - `Q:IN:H:A:M:XDC:A` — India HH, INR bn → **161,573.0** (≈ INR 161.6tn); `Q:IN:N:A:M:XDC:A` → 184,337.8
  - `Q:GB:H:A:M:XDC:A` — UK HH, GBP bn → 2,237.6; `Q:JP:H:A:M:XDC:A` — JP HH, JPY bn → 405,717.1
- **Verified**: ✅ 2026-08-19 — HTTP 200, zip parsed, 1,133 rows, values above extracted from the file.
- **Notes & pitfalls**: Wide format (period = column) → reshape to long. Header rows carry duplicate code+label column pairs (`BORROWERS_CTY` / `Borrowers' country`). `UNIT_TYPE=770` = % of GDP; `XDC` rows use each country's own currency with `UNIT_MEASURE` naming it. DBnomics mirrors this dataset (`BIS/WS_TC`, series like `Q.US.H.A.M.770.A`) but with ~3 quarters' mirror lag — prefer the bulk zip. No monthly frequency in WS_TC; for monthly national detail use the national cards below.

## Federal Reserve — Z.1 Financial Accounts (via DBnomics mirror `FED/Z1`)

- **What**: US flow-of-funds **stocks** (levels, L-tables) by sector & instrument: household home mortgages, consumer credit, NFC corporate bonds, NFC loans & other debt, plus total HH and NFC debt.
- **Coverage**: United States only (sectoral depth unmatched elsewhere).
- **Frequency & lag**: Quarterly. Latest observation seen: **2026-03-31** (probed 2026-08-19) — note the mirror index (2026-06-12) may lag upstream by a quarter; Z.1 releases ~10 weeks after quarter-end.
- **Access**: `https://api.db.nomics.world/v22/series/FED/Z1/{SERIES_CODE}.Q?observations=1` — keyless JSON. Dataset: 39,650 series, indexed 2026-06-12. Direct federalreserve.gov DDP returns HTTP 400 (retired); FRED needs key/HTTPS workarounds (above) — DBnomics is the cleanest route.
- **License & cost**: US government public domain (upstream); DBnomics free keyless.
- **Sample series** (seen 2026-08-19, all 2026-03-31, USD millions):
  - `FL153165105.Q` — HH home mortgages → **13,820,984** (≈ $13.8tn)
  - `FL153166000.Q` — HH consumer credit → **5,073,031** (≈ $5.1tn)
  - `FL104104005.Q` — NFC corporate bonds → **14,493,652** (≈ $14.5tn)
  - `FL104190005.Q` — NFC loans & other loans/liabilities → **31,907,368** (≈ $31.9tn)
- **Verified**: ✅ 2026-08-19 — HTTP 200 on all four series, values parsed from JSON.
- **Notes & pitfalls**: `FL…` codes: 1st–2nd digit type (10=liability), then sector (53=households & NPISHs, 10=nonfin corporate) then instrument. L-tables are end-of-quarter levels; stock-vs-flow confusion with `FA…` codes is the classic mistake. Mirror lag: if a newer quarter is out, check upstream Z.1 release before blaming the pipeline.

## Federal Reserve — H.8 Assets & Liabilities of Commercial Banks (via DBnomics `FED/H8`)

- **What**: Weekly US commercial-bank balance sheet — bank credit, loans & leases, securities. US *banking-system* debt holdings, not private-sector debt per se; complements Z.1 as the high-frequency US credit signal.
- **Coverage**: US commercial banks (seasonally adjusted, weekly average).
- **Frequency & lag**: Weekly. Latest observation seen: **2026-08-05** (probed 2026-08-19).
- **Access**: `https://api.db.nomics.world/v22/series/FED/H8/B1001NCBA?observations=1` — keyless.
- **License & cost**: Public domain; DBnomics free keyless.
- **Sample series**: `FED/H8/B1001NCBA` — bank credit, weekly, 2026-08-05 = **19,780,811.3** USD mn (≈ $19.8tn).
- **Verified**: ✅ 2026-08-19 — HTTP 200, value parsed.
- **Notes & pitfalls**: Series-code suffixes encode SA/NSA and break-adjustment; confirm the variant before chaining. Not a private-debt stock in the sector-accounts sense — use for weekly momentum only; Z.1/BIS for levels.

## ECB — BSI: Monthly MFI Balance Sheet, loans to households & NFCs (keyless SDMX)

- **What**: Amounts outstanding of euro-area monetary financial institutions' loans: households total / house purchase / consumer credit, and NFC loans. Monthly, keyless — the fastest official euro-area private-credit gauge.
- **Coverage**: Euro area aggregates (REF_AREA=U2, changing composition) + national series (REF_AREA=DE, FR, IT, … verified DE).
- **Frequency & lag**: Monthly. Latest observation seen: **2026-06** (probed 2026-08-19) → ≈ 6-week lag.
- **Access**: `https://data-api.ecb.europa.eu/service/data/BSI/{key}?format=csvdata&lastNObservations=1` — keyless CSV, no registration. Key template: `M.{REF_AREA}.N.U.A{acct}.A.1.U2.{item}.{CURRENCY_TRANS}.E`, where accounting-activity `A20` = loans to households, `A22` = house purchase, `A21` = consumer credit, `2240` = loans to NFCs. **`CURRENCY_TRANS=Z01` (all currencies) is the non-obvious code** for aggregates; national series use `EUR`.
- **License & cost**: Free, keyless (ECB reuse policy, attribution).
- **Sample series** (seen 2026-08-19, all 2026-06, EUR millions):
  - `M.U2.N.U.A20.A.1.U2.2250.Z01.E` — EA HH loans → **6,971,164** (≈ €7.0tn)
  - `M.U2.N.U.A22.A.1.U2.2250.Z01.E` — EA HH house-purchase → **5,504,495**
  - `M.U2.N.U.A21.A.1.U2.2250.Z01.E` — EA HH consumer credit → **805,933**
  - `M.U2.N.U.A20.A.1.U2.2240.Z01.E` — EA NFC loans → **5,441,792**
  - `M.DE.N.A.A20.A.1.U2.2250.EUR.E` — Germany HH loans → **2,111,781**
- **Verified**: ✅ 2026-08-19 — HTTP 200, values parsed from CSV responses.
- **Notes & pitfalls**: BSI counts only **MFI loans** — debt securities issued by NFCs are not here (use QSA/bond data for those). U2 = changing composition (back series not spliced across EU enlargements). The endpoint also accepts `startPeriod=`/`endPeriod=`; `lastNObservations=1` is enough for the dashboard probe. ECB's SDMX is authoritative & fresh — skip DBnomics's ECB mirror (indexed 2026-07-25, i.e. monthly refresh but no gain).

## ECB — QSA: Quarterly Sector Accounts, debt stocks (keyless SDMX)

- **What**: Euro-area sector-account **stocks** (`STO=LE` = liabilities, end-of-period): HH loans (F4), NFC loans (F4), NFC debt securities (F3), in EUR (XDC). Balance-sheet-consistent counterpart to BSI, includes non-MFI lenders.
- **Coverage**: Euro area aggregate (REF_AREA=**I9**), EA19 (I8), plus member countries.
- **Frequency & lag**: Quarterly. Latest observation seen: **2025-Q4** (probed 2026-08-19) → ≈ 5-month lag (quarterly release ~April/+Q+1).
- **Access**: `https://data-api.ecb.europa.eu/service/data/QSA/{key}?format=csvdata&lastNObservations=1` — keyless CSV (same host as BSI, different flow). Key template: `Q.{REF_AREA}.W0.{sector=S1M|S11}.{counterpart=S1}.N.LE.{instrument}.{maturity=T}.{valuation=_Z}.XDC._T.S.V.N._T`.
- **License & cost**: Free, keyless.
- **Sample series** (seen 2026-08-19, all 2025-Q4, EUR millions):
  - `Q.I9.W0.S1M.S1.N.LE.F4.T._Z.XDC._T.S.V.N._T` — EA HH loans → **7,991,103.5** (≈ €8.0tn)
  - `Q.I9.W0.S11.S1.N.LE.F3.T._Z.XDC._T.S.V.N._T` — EA NFC debt securities → **1,953,842.5**
  - `Q.I9.W0.S11.S1.N.LE.F4.T._Z.XDC._T.S.V.N._T` — EA NFC loans → **14,371,902**
- **Verified**: ✅ 2026-08-19 — HTTP 200, values parsed.
- **Notes & pitfalls**: **EA aggregate REF_AREA is `I9`, not `U2` (U2 → 404)** — tripped over repeatedly. `I8` (EA19 fixed) series exist but many **end 2022-Q4**; always prefer I9. `STO=LE` selects stocks; without it you may get transactions (F-topic). S1M = households+NPISHs, S11 = NFCs.

## Eurostat — nasq_10_f_bs (quarterly financial balance sheets)

- **What**: EU/EA quarterly **financial balance sheets** by sector & instrument (HH and NFC debt, F3/F4), the Eurostat counterpart to ECB QSA with full country coverage.
- **Coverage**: 30 geos (EA20, EA21, EU27, member states), quarterly.
- **Frequency & lag**: Quarterly; **2026-Q1 present** in the dataset (seen 2026-08-19).
- **Access**: Dataset-level: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nasq_10_f_bs?format=JSON&lang=en` → HTTP **200**. Series-level filter `…&sector=S14_S15&na_item=F4…` → HTTP **400** (unresolved dimension-value combo — the code combination is not accepted by the API even though it appears in the dimension list).
- **License & cost**: Free, keyless (Eurostat reuse policy).
- **Sample series**: none extracted — dataset-level 200 confirmed (30 geos, 2026-Q1) but no valid series filter resolved this session.
- **Verified**: ⚠️ Partially verified 2026-08-19 — dataset endpoint live; **series extraction unconfirmed** (400 on the S14_S15×F4 filter).
- **Notes & pitfalls**: Treat as unproven until the filter works. Likely fix: pull the full dataset JSON (it is small enough) and filter client-side on `sector`/`na_item`/`unit` dimensions rather than server-side parameters; or use ECB QSA (I9) + national BSI instead, which already covers EA aggregates + DE at monthly frequency. Do not promise Eurostat numbers on the dashboard without that follow-up.

## IMF IFS (via DBnomics `IMF/IFS`) — China monthly claims on private sector

- **What**: "Claims on Private Sector" (domestic credit extended by banks/monetary survey to private non-financial borrowers), national currency — the closest keyless monthly proxy for PBOC aggregate-financing/RMB-loan stocks. Includes `32D` monetary survey, `22D` banking institutions, `12D` monetary authorities variants.
- **Coverage**: ~190 IFS countries incl. CN, IN (bank-claims side only; no HH/NFC split, no bonds).
- **Frequency & lag**: Monthly. Latest observation seen: **2025-06** for China (probed 2026-08-19) → mirror lag ≈ 13 months (DBnomics `IMF/IFS` indexing, not the source's fault — IFS itself runs 1–2 months behind).
- **Access**: `https://api.db.nomics.world/v22/series/IMF/IFS/{CODE}?observations=1&limit=1` — keyless. Series search (the reliable route): `/v22/series/IMF/IFS?q=China%20claims%20on%20private%20sector&limit=12`. Note: DBnomics **global** `/v22/series?q=` endpoint rejects the `q` param ("additional properties: ['q']") — only the dataset-scoped form works.
- **License & cost**: Free, keyless (IMF via DBnomics).
- **Sample series** (seen 2026-08-19):
  - `M.CN.32D___XDC` — China claims on private sector, monthly → **2025-06 = 274,305,766.8 CNY mn** (≈ CNY 274.3tn); 367 obs (`M.CN.22D___XDC` identical)
  - `Q.CN.32D___XDC` — quarterly variant → 2025-Q2 = 274,305,766.8
  - `M.IN.22D___XDC` — India claims on private sector → last **2022-05 = 123,249,664.6 INR mn** (≈ INR 123.2tn) — **frozen since 2022** ❌
- **Verified**: ✅ 2026-08-19 (China series, obs fetched) / ⚠️ India stale (ends 2022-05).
- **Notes & pitfalls**: No household-vs-corporate split (PBOC publishes that split monthly on-site, but PBOC's own site is scrape-only with no API — manual/XLSX route for another session). `12D` variant for CN returns zeros — use `32D`/`22D`. Units are national-currency millions. The 13-month DBnomics mirror lag makes this a cross-check/backfill series, not the live feed; for current China levels use BIS WS_TC quarterly (2025-Q4).

## NY Fed — Household Debt & Credit Report (per-product HH stocks): NOT machine-accessible

- **What**: Quarterly US HH debt by product (mortgage, HELOC, auto, student, credit card + delinquencies) — the standard granular US household-debt benchmark.
- **Verified**: ❌ 2026-08-19 — JS-gated. The landing page (`/microeconomics/hhdc`) is a JS app (`{{data_url}}` templates, `cmd-main.js`); **every** `medialibrary/…/data/xls/*.xlsx` URL returns HTTP 200 `text/html` that is byte-similar to the response for a deliberately bogus filename (generic fallback page — soft 404). No CSV/XLSX link discoverable in static HTML; no form/meta-refresh/JS-redirect to follow.
- **Notes & pitfalls**: Treat as a manual-download source (browser → save XLSX) or revisit with a JS-capable fetch (Browser Use session) later. Not a blocker: the same per-product stocks are available from Z.1 (`FL153165105`, `FL153166000`, …) which is keyless; NY Fed adds auto/student/card split + delinquency detail (delinquency = another dossier).

## Bank of England — Monthly Lending to Individuals: NOT machine-accessible this session

- **What**: Monthly UK secured (mortgage) + unsecured (consumer) lending to individuals, amounts outstanding & flows — the UK counterpart to ECB BSI.
- **Verified**: ❌ 2026-08-19 — three routes probed, none yielded data: (1) IADB `https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?Travel=NIxAZxSUx&FromSeries=1&ToSeries=50&D1=MLT…` returns a 17 KB "Data Series | Bank of England | Database" **HTML app shell with zero series content** (JS-loaded); `CSVf=TN/TX` params ignored — still HTML. (2) DBnomics `BOE` provider exists but has only **26 datasets** (external business of banks, capital issuance, …) — **no IADB / lending-to-individuals mirror**; guessed `BOE/IADB/IMLDJOA`-style codes → 404. (3) Guessed release-file patterns (`/-/media/boe-files/statistics/money-and-credit/2026/lending-to-individuals-june-2026.xlsx`) → 404.
- **Notes & pitfalls**: Options for follow-up: BoE IADB with a JS-capable fetch to capture the XHR the app makes; or the BoE Statistical Interactive Database (BieRWB) dynamic CSV export once its series-selection query params are mapped. Until then UK private debt rides on **BIS WS_TC quarterly** (`Q:GB:H…` 2025-Q4 = £2.24tn).

## Bank of Japan — Flow of Funds: no DBnomics mirror

- **What**: Quarterly sector-accounts stocks (HH/corporate loans & CP/bonds), the Japan counterpart to Z.1/QSA.
- **Verified**: ❌ 2026-08-19 — DBnomics `BOJ` provider has only **3 datasets** (`BP` balance of payments, `CGPI`, `SPPI`) — **no Flow of Funds mirror**. BoJ's own time-series site not probed this session (out of probe budget).
- **Notes & pitfalls**: Follow-up: BoJ Time-Series Statistical Data Search (`stat.boj.or.jp`) offers keyless CSV per series — unmapped this session. Until then Japan private debt rides on **BIS WS_TC quarterly** (`Q:JP:H…` 2025-Q4 = ¥405.7tn HH; NFC ¥755.8tn).

## Reserve Bank of India — DBIE: registration required

- **What**: India sectoral credit / bank credit stocks (sector × industry) — the authoritative India source.
- **Verified**: ❌ 2026-08-19 — DBIE (Database on Indian Economy) requires free registration/API key; not probed with credentials. DBnomics has no RBI provider (provider list check).
- **Notes & pitfalls**: Documented fallback chain for India: RBI DBIE (register) → IMF IFS via DBnomics (works but **frozen 2022-05**) → **BIS WS_TC quarterly** (`Q:IN:H…` 2025-Q4 = INR 161.6tn HH; NFC 184.3tn — currently the freshest verified India private-debt feed).

## Country × instrument matrix

Country-by-instrument availability as *verified* on 2026-08-19 (source → frequency → latest obs seen):

| Country | Mortgages / HH total | Consumer credit | Corporate (NFC) loans | Corporate bonds | Private total (%GDP or lvl) | Best freq |
|---|---|---|---|---|---|---|
| US | Z.1 `FL153165105` 2026-03-31 = $13.82tn (mortgages) | Z.1 `FL153166000` 2026-03-31 = $5.07tn | Z.1 `FL104190005` = $31.91tn; H.8 weekly bank credit 2026-08-05 = $19.78tn | Z.1 `FL104104005` = $14.49tn | BIS `Q:US:P:…:770:A` 2025-Q4 = 140.3% | Weekly (H.8) |
| Euro area | ECB BSI `A22` 2026-06 = €5.50tn; QSA S1M F4 2025-Q4 = €7.99tn | ECB BSI `A21` 2026-06 = €0.81tn | ECB BSI `2240` 2026-06 = €5.44tn; QSA S11 F4 2025-Q4 = €14.37tn | QSA S11 F3 2025-Q4 = €1.95tn | BIS `Q:XM:H…USD` 2025-Q4 = $9.39tn (HH) | Monthly (BSI) |
| Germany | ECB BSI `M.DE…A20…` 2026-06 = €2.11tn (HH total) | via BSI A21 national (untested) | via BSI 2240 national (untested) | — | BIS DE rows in WS_TC | Monthly (BSI) |
| UK | BoE lending to individuals — **blocked** (JS-gated; no DBnomics mirror) | — | — | — | BIS `Q:GB:H…XDC` 2025-Q4 = £2.24tn | Quarterly (BIS) |
| Japan | BoJ FoF — **no DBnomics mirror** | — | — | — | BIS `Q:JP:H…XDC` 2025-Q4 = ¥405.7tn (NFC ¥755.8tn) | Quarterly (BIS) |
| China | PBOC split — **scrape-only**; IFS `M.CN.32D` 2025-06 = CNY 274.3tn (total private, no split, 13-mo lag) | — | IFS total only | — | BIS `Q:CN:H…XDC` 2025-Q4 = CNY 81.3tn (NFC 200.1tn) | Monthly (IFS, lagged) |
| India | RBI DBIE — **registration required**; IFS frozen 2022-05 | — | — | — | BIS `Q:IN:H…XDC` 2025-Q4 = INR 161.6tn (NFC 184.3tn) | Quarterly (BIS) |

Instrument-level (mortgage vs consumer) split is currently only verified for US (Z.1) and euro area (ECB BSI A22/A21). For UK/JP/CN/IN the fallback is the BIS HH/NFC quarterly aggregate — no verified monthly split exists for them yet.

## Gaps

- **NY Fed Household Debt & Credit** (auto/student/card split) — **JS-gated**: every medialibrary XLSX URL soft-404s to a generic HTML page identical to a bogus filename's response. Manual browser download or JS-capable fetch needed; Z.1 covers mortgage/consumer split keylessly.
- **Bank of England monthly lending to individuals** — **JS-gated** (IADB HTML shell; `CSVf` param ignored) and **no DBnomics mirror** (BOE provider = 26 datasets, none IADB). Needs a JS-capable fetch to capture the XHR, or manual download from the statistical release page.
- **Japan BoJ flow of funds** — **no DBnomics mirror** (BOJ provider = 3 datasets, no FoF). Follow-up: `stat.boj.or.jp` time-series search keyless CSV, unmapped this session.
- **China PBOC monthly HH vs non-HH RMB loans + TSF** — PBOC site scrape-only (no API); IFS via DBnomics gives total-private monthly but **13-month mirror lag** and no HH/NFC split. Manual XLSX route or JS fetch needed for the split.
- **India RBI DBIE** — registration required. Verified fallback: BIS WS_TC (2025-Q4); IFS mirror frozen 2022-05.
- **Eurostat nasq_10_f_bs** series filter returns 400 on `sector=S14_S15&na_item=F4` — unresolved; fall back to full-dataset JSON + client-side filter or ECB QSA.
- **Monthly private-debt split for UK/JP/CN/IN** — until national sources are resolved, quarterly BIS WS_TC is the only confirmed feed (dashboard monthly rule met only via US H.8 weekly + EA BSI monthly).
