# Sources 04 — Private-Debt Health (Delinquency, NPL, DSR, Charge-offs, Bankruptcies)

Verification probes for the debt-monitor dashboard, health block. Every endpoint below was probed live with a single-file Python `requests` script on **2026-08-19**. Cadence rule: monthly preferred, quarterly accepted, annual only as documented fallback. "Latest obs" = last observation date actually seen in the response/file, not the provider's claimed vintage. Scope: US, euro area/EU, UK, Japan, China, India + cross-country.

Environment notes (inherited from round-1 probes, confirmed): `fred.stlouisfed.org` over HTTPS times out from this host → use **plain HTTP + curl User-Agent** on `fredgraph.csv`. BIS bulk files live at **`data.bis.org/static/bulk/…`** (www.bis.org equivalents 404; `stats.bis.org` serves HTML on bulk paths). ECB data API is keyless at `data-api.ecb.europa.eu`. IMF SDMX 2.1 at `api.imf.org/external/sdmx/2.1`.

## BIS — Debt Service Ratios (WS_DSR, bulk CSV)

- **What**: Debt service ratios (interest + amortisation, % of disposable income for households; % of gross income for NFCs): Households & NPISHs (H), Non-financial corporations (N), Private non-financial sector (P). The cross-country DSR workhorse.
- **Coverage**: **32 borrower countries** incl. US, China, India, UK, Japan, Germany, France, Italy, Spain, Korea, + EMEs (BR, ID, MX, TR, ZA…). **No euro-area aggregate row** (EA members only, country-by-country). All three borrower sectors per country (66 series rows = 32×3 minus a few).
- **Frequency & lag**: Quarterly, 1999-Q1 → **2025-Q4** (last column seen in file 2026-08-19) → lag ≈ 5–7 months.
- **Access**: Bulk zip `https://data.bis.org/static/bulk/WS_DSR_csv_col.zip` (10.5 KB, one wide CSV `WS_DSR_csv_col.csv`, 66 rows, 108 quarter columns). Python: `requests.get` → `zipfile.ZipFile(io.BytesIO(...))` → `csv.DictReader`. **Host must be `data.bis.org`** — the same path on `stats.bis.org` returns HTTP 200 but `text/html` (JS shell, 194 KB, not a zip) — this is exactly the trap the round-1 agent hit.
- **License/cost**: Open, free, keyless (BIS statistics terms of use, attribution).
- **Sample series** (seen 2026-08-19, last cell 2025-Q4): US HH = **8.0**, US NFC = 37.5, US private = 14.1; China private non-financial = **18.8**; India private non-financial = **12.2**; UK HH = 8.8; Japan HH = 7.5, Japan private = 15.5; Germany HH = 5.4, private = 12.2; France HH = 6.0, private = 20.8.
- **Verified**: ✅ Verified live 2026-08-19 — HTTP 200 `application/zip`, zip parsed, all values above read from the file.
- **Notes/pitfalls**: Wide format (period = column) — reshape long before ingest. DSR_BORROWERS codes `{H, N, P}`; % units only (DECIMALS=1). India/China only publish the **private-sector** DSR in this file (no separate HH row) — for CN/IN household DSR there is no BIS series. SDMX v2 data query `https://stats.bis.org/api/v2/data/dataflow/BIS/DSR/1.0/US.Q.R.A.A.M.XR.....` → **404** (confirmed round-1 + not retried; bulk CSV is the working path).

---

## US — Federal Reserve (FRED) charge-off & delinquency rates on bank loans

- **What**: Delinquency (30+ days for consumer, 90+ for some; % of balances) and charge-off rates for US commercial banks, by loan type: credit cards, mortgages (first-lien), consumer loans, C&I, business/CRE, plus charge-offs.
- **Coverage**: US only (aggregate commercial-bank level; no bank-size split in these IDs).
- **Frequency & lag**: Quarterly (quarter-start dates), ~1 quarter lag. Latest obs seen: **2026-01-01 (2026-Q1)** for DRCCLACBS / DRSFRMACBS / DRCLACBS / DRTSCILM / CORCCACBS / DRBLACBS / DRCRELEXFACBS.
- **Access**: Keyless CSV: `http://fred.stlouisfed.org/graph/fredgraph.csv?id={SERIES}` — **plain HTTP + curl User-Agent** (`{'User-Agent':'curl/8.5.0'}`); HTTPS times out from this host. Official `api.stlouisfed.org` needs a free key.
- **License/cost**: Free, keyless on fredgraph.csv.
- **Sample series** (seen 2026-08-19, quarterly, last obs 2026-Q1 unless noted):
  - `DRCCLACBS` CC delinquency 90+ %bal: 2025-Q3 2.98 → 2025-Q4 2.94 → **2026-Q1 2.92**
  - `DRSFRMACBS` mortgage delinq %bal: **2026-Q1 1.89** (prior 1.79)
  - `DRCLACBS` consumer loans delinq: **2026-Q1 2.64**
  - `DRTSCILM` C&I delinq (NOT SA): **2026-Q1 5.3** — but 2025-Q2 = 18.5, 2026-Q3 = 0.0 (see pitfalls)
  - `CORCCACBS` CC charge-off rate: **2026-Q1 3.84** (prior 4.07)
  - `DRBLACBS` business loans delinq: **2026-Q1 1.34**; `DRCRELEXFACBS` CRE: **2026-Q1 1.56**
- **Verified**: ✅ Verified live 2026-08-19 — all 7 series HTTP 200 with observations through 2026-Q1.
- **Notes/pitfalls**: `DRTSCILM` (C&I, NSA) has extreme spikes (18.5 in 2025-Q2, 0.0 in 2026-Q3-partial) — 0.0 values are placeholder/early-vintage artifacts, not real delinquency; filter or use SA variant. Auto delinq `DRCARACBS`, other-consumer `DRTOLACBS`, `CORBAACBS` → **404** (not on FRED under these IDs). Quarterly-only at bank level; the monthly household delinquency detail lives in NY Fed HHDC (next card).

## US — NY Fed Household Debt and Credit Report (HHDC)

- **What**: Household delinquency by product (mortgage, auto, credit card, student), 90+ days % of balances, transition rates, and total debt composition, from Equifax microdata.
- **Probe result (2026-08-19)**: page `https://www.newyorkfed.org/microeconomics/hhdc` is a **JS app — 0 static xlsx/csv/zip links**; `…/medialibrary/interactives/creditcardmap/data/` → 404. Data files (historically `household-debt-and-credit-report…xlsx`) are behind the JS app; exact URLs rotate per quarter.
- **Frequency & lag**: Quarterly, ~5–6 weeks after quarter-end.
- **Access**: Web page (human) + embedded data files; no API. Pattern to try: `https://www.newyorkfed.org/medialibrary/interactives/hhdc/csv/hhdc.csv` (unverified). Fallback for auto/student delinquency detail: FRED quarterly bank-level series (card above) lacks auto split; student/auto delinq detail → NY Fed report PDF/XLSX manual download (gated on this host for automation, fine for human).
- **License/cost**: Free, public domain (US Fed).
- **Sample series**: none seen programmatically (page links empty). Latest report known externally: 2026-Q1 report (August 2026 vintage). **Not machine-verified on 2026-08-19.**
- **Verified**: ⚠️ Page reachable (200) but data files not machine-accessible; **latest obs NOT verified** — treat as human-download-only source until a stable URL is found.
- **Notes/pathforward**: Try the quarterly report page HTML for `medialibrary` links (rotate); or use `https://www.newyorkfed.org/microeconomics/hhdc/downloads` if it exists. Bank-level Fed series above are the automatable proxy.

## ECB / SSM — Supervisory Banking Statistics (SUP) — via DBnomics mirror

- **What**: SSM significant+less-significant institution data: **non-performing exposures (NPE) stocks** by sector (NFC S11 / households etc.), coverage, provisioning, plus ratio items (`I…` codes, %). The euro-area bank-health workhorse, per supervisory country.
- **Coverage**: All SSM countries (AT, BE, DE, FR, …) × sector (S11 NFC, S14 HH…) × institution type (ALL/SII significant/LSI less-significant) × item (E0035/E0036 NPE stocks…).
- **Frequency & lag**: Quarterly (H = half-yearly for some items). Latest obs seen: **2026-Q1** (5 quarters available 2025-Q1→2026-Q1 in mirror) → ≈ 4–5 month lag.
- **Access**: **DBnomics mirror `ECB/SUP`** (dataset "Supervisory Banking Statistics", verified listed): `https://api.db.nomics.world/v22/series/ECB/SUP/{CODE}?observations=1&format=json`. Series-key grammar: `Q.{REF_AREA}.W0.{SECTOR}.{ITEM}._T.{ALL|SII|LSI}._Z.{N_|_Z}.{LE|…}.{E|PCT}.C`. Upstream: landing page `https://www.bankingsupervision.europa.eu/press/publications/supervisory_banking_statistics/html/index.en.html` → **404 JS shell** (0 file links, both curl and browser UA); direct ECB data portal flow `…/service/data/SBS` → 404 "No results found" (SBS ≠ SUP; SUP itself is not on data-api.ecb.europa.eu — the DBnomics mirror is the machine path).
- **License/cost**: Free, keyless (ECB reprint terms; DBnomics free).
- **Sample series** (seen 2026-08-19): `Q.DE.W0.S11.E0035._T.ALL._Z.N_.LE.E.C` (Germany, NFC-sector NPE stock, EUR bn): 2025-Q4 = **66.82** → **2026-Q1 = 66.16**; `Q.DE.W0.S11.E0036._T.ALL._Z.N_.LE.E.C`: 2025-Q4 = 33.05 → **2026-Q1 = 32.51**.
- **Verified**: ✅ Verified live 2026-08-19 via DBnomics (dataset listing + observations through 2026-Q1). Upstream landing page broken-for-automation.
- **Notes/pitfalls**: E-item codes are NPE **stocks in EUR**, not ratios — exact mapping of E0035/E0036 to loan sectors comes from the long `series_name` (read it; don't guess). The NPL **ratio** items are `I7xxx` (% codes) but the exact item id was not pinned this session (search returned truncated names) — resolve via `/v22/series/ECB/SUP?q=non-performing ratio` before ingest. No pre-computed euro-area aggregate row found (data is by reporting country); aggregate yourself or use the ECB "NPL timeline" (not probed). Mirror `indexed_at` check recommended each pull.

## EBA — Risk Dashboard

- **What**: Quarterly EU-wide bank risk indicators: NPL ratio, stage-2 loans, forbearance, IFRS 9 coverage, by country and portfolio.
- **Coverage**: EU/EEA banks (EBA sample), all member states.
- **Frequency & lag**: Quarterly, ~1 quarter.
- **Access**: `https://www.eba.europa.eu/risk-and-data-analysis/risk-analysis/risk-dashboard` → **404 JS shell** (10.5 KB, 0 file links; curl and browser UA alike, probed 2026-08-19). The xlsx/zip URLs are generated client-side and rotate per quarter; no API.
- **License/cost**: Free (human access).
- **Sample series**: none machine-extracted. **Latest obs NOT verified.**
- **Verified**: ❌ Not verifiable from this host on 2026-08-19 (landing 404-shell, no static file links).
- **Notes/pitfalls**: If needed, use the browser tool (JS rendering) once per quarter to resolve the file URL, then fetch it headlessly; or substitute ECB SUP (card above) for NPL/NPE and skip stage-2/forbearance. Historical risk-dashboard xlsx URLs follow `https://www.eba.europa.eu/sites/default/files/document_library/Publications/Risk_analysis/Risk_Dashboard/…` but the exact filenames rotate.

## IMF — Financial Soundness Indicators (FSI), NPL ratio (via DBnomics mirror)

- **What**: Bank **NPL ratio (% of gross loans, `FSANL_PT`)** and the wider FSI set (regulatory capital, liquidity, etc.), incl. quarterly for many reporters.
- **Coverage**: ~100+ reporters. Verified: US, CN, IN, GB, DE, FR (quarterly) + JP (quarterly only; annual 404). No euro-area aggregate (`A.XM` → 404).
- **Frequency & lag**: Annual (`A.{CTY}.FSANL_PT`) and **quarterly** (`Q.{CTY}.FSANL_PT`) both exist. Latest seen: **2025-Q1** for CN/IN/DE/GB; 2024-Q3 US; 2024-Q3 JP (mirror dated 2025-08-31 → real upstream may be fresher).
- **Access**: DBnomics mirror `IMF/FSI`: `https://api.db.nomics.world/v22/series/IMF/FSI/{FREQ}.{CTY}.FSANL_PT?observations=1&format=json` (keyless).
- **License/cost**: Free, keyless.
- **Sample series** (seen 2026-08-19): `Q.GB.FSANL_PT` 2025-Q1 = **0.977**; `Q.CN.FSANL_PT` 2025-Q1 = **1.513**; `Q.IN.FSANL_PT` 2025-Q1 = **2.344**; `Q.DE.FSANL_PT` 2025-Q1 = **1.734**; `Q.US.FSANL_PT` 2024-Q3 = 0.935; `Q.JP.FSANL_PT` 2024-Q3 = **1.210**; annual 2024: CN 1.505, IN 2.500, GB 1.019, DE 1.772, FR 2.087, US 2023 0.847.
- **Verified**: ✅ Verified live 2026-08-19 (10+ series with observations).
- **Notes/pitfalls**: Direct api.imf.org SDMX for FSI: flow list has `FSIC`/`FSIBSIS`/`FSICDM` but **`data/FSIC/USA.PNPL_T1.A` returns a valid SDMX envelope with ZERO observations** (empty dataset — indicator key unproven); don't use it. Quarterly coverage is irregular (US gaps: 63 obs incl. missing quarters; JP ends 2024-Q3). Values match WB FB.AST.NPER.ZS exactly (same underlying IMF source).

## World Bank — Bank NPL ratio (FB.AST.NPER.ZS) — annual fallback

- **What**: Bank NPLs to total gross loans (%), all economies — the claim-validation target.
- **Coverage**: ~217 economies + aggregates (795 rows for 2023–2025).
- **Frequency & lag**: **ANNUAL confirmed** (`date` = years only; probe of 2023:2025 window shows year keys). Latest: **2025** for USA/IND/GBR; **2024** for CHN (2025 null); DB `lastupdated` = 2026-07-13.
- **Access**: `https://api.worldbank.org/v2/country/{ISO3;…}/indicator/FB.AST.NPER.ZS?format=json&date=2023:2025` (keyless, verified 200).
- **License/cost**: Open CC-BY-4.0, keyless.
- **Sample series** (seen 2026-08-19): USA 2025 = **0.960**, IND 2025 = **2.063**, GBR 2025 = **0.948**, CHN 2024 = **1.505** (CHN 2025 null).
- **Verified**: ✅ Verified live 2026-08-19.
- **Notes/pitfalls**: Annual only → **documented fallback**, not the health pipe. China lags one extra year. Identical numbers exist quarterly via IMF FSI (card above) — prefer FSI for cadence; keep WB for country breadth.

## National sources — China NFRA, India RBI, Japan (honest bounds)

- **What**: CN NFRA quarterly commercial-bank NPL; IN RBI FSR GNPA (half-yearly); JP FSA/BoJ loan-quality.
- **Probe results (2026-08-19)**: NFRA page `https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html…` → **200, 20 KB HTML** but data tables are JS-rendered/rotating doc ids — no machine-readable series extracted. RBI FSR list `https://www.rbi.org.in/Scripts/PublicationsList.aspx?head=Financial%20Stability%20Report` → **200, 55 KB HTML, 0 GNPA data rows** (list page only; FSR is a PDF per half-year). Japan: not probed directly; **IMF FSI covers JP quarterly** (Q.JP 2024-Q3 = 1.210).
- **Frequency & lag**: NFRA quarterly; RBI FSR half-yearly (Jun/Dec); JP quarterly via FSI.
- **Verified**: ⚠️ Pages reachable but **no observations extracted** — treat all three as manual/human sources; automatable substitutes: IMF FSI (CN→2025-Q1, IN→2025-Q1, JP→2024-Q3) + WB annual.
- **Notes/pitfalls**: Don't hardcode nfra.gov.cn docIds. RBI DBIE (`dbie.rbi.org.in`) requires free registration — untested here. GNPA is for scheduled commercial banks (SCBs); FSI IN series matches SCB GNPA closely.

## UK — BoE mortgage arrears/possessions (MLAR) + Eurostat arrears survey

- **What**: BoE/MLAR mortgage arrears (>2.5%/possession orders) — the UK household-health series; FCA statistics; Eurostat ILC arrears (survey).
- **Probe results (2026-08-19)**: DBnomics search "MLAR" / "mortgage possessions" / "arrears mortgage" → **0 BoE hits** (only Eurostat `ILC_MDES05/06`, `HLTH_DM050` household-arrears survey series). BoE provider on DBnomics (26 datasets) holds only external-business/industrial lending series (indexed 2026-06) — no MLAR mirror.
- **Frequency & lag**: MLAR quarterly upstream (unverified here).
- **Verified**: ❌ No machine path verified. UK health metrics available today: BIS DSR (GB HH 2025-Q4 = 8.8) + IMF FSI Q.GB NPL (2025-Q1 = 0.977) + WB (2025 = 0.948).
- **Notes/pitfalls**: BoE's own IADB/MLAR data at `bankofengland.co.uk` is behind a JS download portal; probe with the browser tool in a later round or hand-download quarterly CSV.

---

## Validation of prior claims

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | "World Bank FB.AST.NPER.ZS is an excellent global proxy" | **PARTLY TRUE → annual fallback only.** Confirmed live, 217 economies, latest 2025 (US/IN/GB) / 2024 (CN), DB updated 2026-07-13. But **annual only** (year keys confirmed) → fails monthly/quarterly cadence; China lags to 2024. Quarterly equivalent exists via IMF FSI `Q.{CTY}.FSANL_PT` (same IMF-sourced numbers, e.g. Q.CN 2025-Q1 = 1.513 vs WB CHN 2024 = 1.505). Use WB for breadth, FSI for cadence. | WB API 200 (USA 2025=0.960, IND=2.063, GBR=0.948, CHN 2024=1.505); DBnomics IMF/FSI obs |
| 2 | "CN & IN NPL partially available via WB/FRED/DBnomics" | **TRUE via WB + DBnomics/IMF-FSI; FRED: no.** CN quarterly NPL `Q.CN.FSANL_PT` through **2025-Q1 = 1.513**; IN `Q.IN.FSANL_PT` through **2025-Q1 = 2.344** (WB annual CHN 2024=1.5046, IND 2025=2.0628 confirmed). FRED: no CN/IN NPL series (only US bank delinq/charge-off). NFRA/RBI native pages reachable but not machine-parseable this session. | DBnomics FSI obs; WB API; FRED probes |
| — | Round-1 hypothesis: BIS DSR bulk works at `data.bis.org` (following WS_TC pattern) | **CONFIRMED.** `https://data.bis.org/static/bulk/WS_DSR_csv_col.zip` → 200 `application/zip`, 10.5 KB, 66 series, 32 countries, quarterly to **2025-Q4**; `stats.bis.org` same path returns HTML — exactly as hypothesized. | Probe 1 |
| — | Round-1 failure: BIS SDMX v2 `stats.bis.org/api/v2/data/dataflow/BIS/DSR/1.0/US.Q.R.A.A.M.XR.....` → 404 | **Consistent — bulk CSV is the path.** Not retried (round-1 result stands); DSR via bulk zip works. | Round-1 log + bulk success |

## Country × metric matrix

| Country | Delinquency (HH) | NPL (banks) | DSR (HH / private) | Charge-offs | Stage-2/forbearance | Bankruptcies |
|---|---|---|---|---|---|---|
| **US** | FRED DRCCLACBS 2.92 (2026-Q1), DRSFRMACBS 1.89, DRCLACBS 2.64; NY Fed HHDC (manual) | FSI Q.US 0.935 (2024-Q3); WB 0.960 (2025) | BIS HH **8.0** (2025-Q4) | CORCCACBS 3.84 (2026-Q1) | — (not in probed sets) | ❌ no FRED quarterly ID found (NBDI* 404) |
| **Euro area / EU** | — | ECB SUP NPE stocks to 2026-Q1 (DE NFC 66.2bn); NPL ratio item I7xxx not pinned | BIS: no EA aggregate; DE 5.4 / FR 6.0 (2025-Q4) | — | EBA RD ❌ (page dead-for-automation) | — |
| **UK** | — (MLAR ❌ no mirror) | FSI Q.GB 0.977 (2025-Q1); WB 0.948 (2025) | BIS HH **8.8** (2025-Q4) | — | — | — |
| **Japan** | — | FSI Q.JP **1.210 (2024-Q3)**; annual FSI 404 | BIS HH 7.5 (2025-Q4) | — | — | — |
| **China** | — | FSI Q.CN **1.513 (2025-Q1)**; WB 1.505 (2024); NFRA manual | BIS private-only **18.8** (2025-Q4); no HH DSR | — | — | — |
| **India** | — | FSI Q.IN **2.344 (2025-Q1)**; WB 2.063 (2025); RBI FSR manual | BIS private-only **12.2** (2025-Q4); no HH DSR | — | — | — |

**Cross-country stack (verified today)**: BIS DSR bulk (32 countries, 2025-Q4) + IMF FSI quarterly NPL (CN/IN/GB/DE → 2025-Q1; US/JP → 2024-Q3) + WB NPL annual (217 economies) + FRED US detail (2026-Q1) + ECB SUP NPE (EA members, 2026-Q1).

## Gaps

1. **Household delinquency outside the US** — no machine-verified monthly/quarterly HH delinquency by product for EA/UK/JP/CN/IN. ECB MIR has no delinquency; EBA RD (stage-2/forbearance) page is automation-dead; BoE MLAR not mirrored. → Next round: browser-tool scrape of EBA RD + BoE IADB, or accept NPL+DSR as the non-US health proxy.
2. **ECB SUP NPL *ratio* item code unpinned** — E0035/E0036 are NPE stocks (EUR); the `I7xxx` ratio item needs one more query to pin (names truncated in search results). Until then EA NPL ratio = compute NPE/loans or use FSI DE/FR/IT quarterly.
3. **BIS DSR lacks euro-area aggregate + CN/IN HH split** — EA must be aggregated from members; CN/IN publish private-sector DSR only.
4. **No quarterly bankruptcy series verified** (US NBDI* 404 on FRED; AO/US Courts not probed — likely manual).
5. **IMF FSI mirror lag** — DBnomics `indexed_at` 2025-08-31, FSI Q.US ends 2024-Q3, Q.JP 2024-Q3; upstream IMF FAS may be fresher but FSIC SDMX keys unresolved (empty datasets).
6. **NY Fed HHDC** — auto/student loan delinquency detail locked behind JS app; no stable CSV URL found.
7. **China NFRA & India RBI** — pages reachable, data not machine-extractable (JS/rotating docIds/PDF). FSI quarterly is the substitute but caps at 2025-Q1.

