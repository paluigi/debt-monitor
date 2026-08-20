# Debt Monitor — Source Dossier 02: Government Debt STOCKS

Central + state + local government debt stocks for US, euro area/EU, UK, Japan, China, India (+ cross-country coverage). Cadence rule: monthly preferred, quarterly accepted, annual = documented fallback only. "Last obs" = latest observation date actually seen in the response, not the provider's claimed vintage.

All probes run 2026-08-19 (UTC) from this host with Python `requests` (fetch + parse in one script; scripts in `/home/ubuntu/probes/p*.py`). Environment notes carried over from dossier 01: **FRED HTTPS and www.imf.org datamapper are blocked from this host** — plain-HTTP FRED and api.imf.org SDMX alternates verified below.

---

## US Treasury (Fiscal Data) — Debt to the Penny (daily, official)

- **What**: Total public debt outstanding, split debt held by the public vs intragovernmental holdings, **daily**. The authoritative US federal debt stock.
- **Coverage**: US federal government only (no state/local). History from 2005-04 (this endpoint).
- **Frequency & lag**: Daily (business days), ~1 business day lag.
- **Access (exact endpoint + working params)**: Keyless JSON:
  `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny?sort=-record_date&page[size]=3`
  Note the service prefix is **`fiscal_service/v2`** — `fiscal_account`, `fiscal_accounting` prefixes all 404. Fields: `record_date`, `debt_held_public_amt`, `intragov_hold_amt`, `tot_pub_debt_out_amt`.
- **License & cost**: Public domain (US federal). Free, keyless.
- **Sample series** (seen 2026-08-19): `record_date=2026-08-17` → total **$39,986,657,878,071.92** ($32,227.2bn public + $7,759.5bn intragov); 2026-08-14 total $39,933.6bn.
- **Verified**: ✅ 2026-08-19 — HTTP 200, 3 newest records parsed.
- **Notes & pitfalls**: Use `page[size]` (bracket-encoding optional). Amounts are strings — cast to float. The Monthly Treasury Statement "debt to the nickel" endpoint was NOT found on the current API — treat MTS debt tables as unverified.

## BIS — Total Credit to Government (WS_TC bulk, quarterly, 48 countries)

- **What**: Credit to **general government** (core debt: loans + debt securities) from all sectors, break-adjusted. Levels in XDC (domestic currency, bn), USD bn, and **% of GDP (UNIT_TYPE `770`)**; nominal (N) and market (M) valuation.
- **Coverage**: 48 borrowers' countries incl. **US, CN, IN, JP, GB, DE, FR, IT**, euro area (XM), G20 (4T), AE/EME aggregates. Government = `TC_BORROWERS='G'`; `FREQ='Q'` only for gov rows.
- **Frequency & lag**: **Quarterly**; latest observation **2025-Q4** (seen 2026-08-19) ≈ 2-quarter lag. One download covers everything.
- **Access (exact endpoint + working params)**: `https://data.bis.org/static/bulk/WS_TC_csv_col.zip` (674 KB; 1,133 wide rows, periods as columns 1940-Q2…2025-Q4). Python: `requests.get` → `zipfile.ZipFile(io.BytesIO(...))` → `csv.DictReader` on `WS_TC_csv_col.csv` (`utf-8-sig`). Filter `TC_BORROWERS=='G' & TC_LENDERS=='A'`.
- **License & cost**: Free, keyless, no registration; BIS terms of use (attribution).
- **Sample series** (seen 2026-08-19, last cell **2025-Q4**, %GDP nominal/from-all-sectors): US **116.4**; JP **194.5**; CN **99.3**; IN **83.9**; GB **102.2**; DE **63.4**; FR **116.0**; IT **137.1**. Market-value %GDP: US 111.0, JP 178.8, GB 88.8, DE 58.9, FR 108.1, IT 137.6. XDC levels: JP 1,290,617.2bn; CN 139,119.3bn; IN 283,460.7bn; US(XDC=USD) 35,797.3bn.
- **Verified**: ✅ 2026-08-19 — HTTP 200, zip parsed, gov rows for all 8 target countries at 2025-Q4.
- **Notes & pitfalls**: Wide format (period = column) — reshape. Columns come in code+label pairs; filter on code columns. UNIT_TYPE: `770`=%GDP, `799`=ratio, `XDC`=LC, `USD`; VALUATION: `N`=nominal, `M`=market. BIS "credit to government" ≠ Maastricht debt — use Eurostat for EU headline. Host **data.bis.org** only.

## Eurostat — EDP Maastricht debt (gov_10dd_edpt1)

- **What**: General government gross debt (Maastricht EDP definition, `na_item=GD`, `sector=S13`): consolidated nominal value at end-of-period, in %GDP (`PC_GDP`) or €mn (`MIO_EUR`).
- **Coverage**: EA20, EU27_2020, + all Member States.
- **Frequency & lag**: ⚠️ **This API table now exposes ANNUAL frequency only** (`freq` dimension = {A}); the classic quarterly EDP transmission (2025-Q4/2026-Q1 notifications) is not served here. Annual data through **2025** is present. Use OECD PSD (below) or BIS for EU quarterly.
- **Access (exact endpoint + working params)**: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10dd_edpt1?format=JSON&lang=EN&na_item=GD&sector=S13&unit=PC_GDP&geo=EA20&sinceTimePeriod=2023` (repeat `geo=` per country or one request per geo — keys omit singleton dims, so multi-geo parsing is fiddly; one-geo-per-request is unambiguous). `freq=Q` returns sizes `[0,...]` = empty; `lastTimePeriod` + `sinceTimePeriod` together → HTTP 400.
- **License & cost**: Free, keyless (Eurostat reuse policy).
- **Sample series** (seen 2026-08-19, annual %GDP): EA20 2023/2024/**2025** = 86.9/87.0/**87.8**; EU27 2025 = 81.7; DE 2025 = 63.5; FR 2025 = 115.6; IT 2025 = 137.1. EA20 €mn 2025 = 13,911,078.9.
- **Verified**: ✅ 2026-08-19 — HTTP 200 on annual %GDP + MIO_EUR queries; ⚠️ quarterly NOT available via this table.
- **Notes & pitfalls**: JSON `value` keys index only non-singleton dimensions (single-geo request → key = time index alone). 2025 annual already published (April 2026 EDP notification). `gov_10a_dd_edpt1` and `tesem1100` = 404.

## OECD — Quarterly Public Sector Debt (via DBnomics mirror)

- **What**: Consolidated public-sector debt stocks by subsector (S13 general government, S11001 central gov, etc., plus total S1), incl. % of GDP (`PT_B1GQ`), domestic currency (`XDC`), USD — from OECD NASEC20 `DF_T7PSD_Q` ("Quarterly Public Sector Debt, consolidated").
- **Coverage**: OECD+ countries incl. **GBR, JPN, USA**, EU members; 7,989 series total, S13 series confirmed for GBR (66), JPN (69), USA (84). No China/India.
- **Frequency & lag**: **Quarterly**; S13 %GDP series last obs **2025-Q4** (seen 2026-08-19).
- **Access (exact endpoint + working params)**: DBnomics API (free, keyless):
  listing `https://api.db.nomics.world/v22/series/OECD/DSD_NASEC20@DF_T7PSD_Q?limit=200&q=GBR+government`
  observations `https://api.db.nomics.world/v22/series/OECD/DSD_NASEC20@DF_T7PSD_Q/Q.N.GBR.W.S13.S1.C.L.LE.F12.LL.PT_B1GQ._T.N.V.N.PSD.INST?observations=1&format=json` → `series.docs[0].period[]` / `.value[]`.
- **License & cost**: Free, keyless (DBnomics + OECD terms).
- **Sample series** (seen 2026-08-19, last obs 2025-Q4): GBR S13 `...F12.LL.PT_B1GQ...` = 1.0; JPN = 1.3; USA = 0.5; GBR series has 121 quarterly obs.
- **Verified**: ✅ 2026-08-19 — HTTP 200, observations parsed. ⚠️ **Dimension semantics unconfirmed**: the `F12.LL` (debt securities/liabilities?) variant returns ratio-scale values (~1.0 for GBR ≈ 100%?) but USA 0.5 doesn't match any expected aggregate — map the full dimension tree (F12 vs F2, LE vs others) before production use.
- **Notes & pitfalls**: OECD's own SDMX portal was probed indirectly only; DBnomics mirror is the reliable keyless route. The `q=` filter searches names, not codes — filter `series_code` for `.S13.` yourself.

## FRED — Federal, state & local debt (plain-HTTP workaround)

- **What**: US federal gross debt quarterly (levels + %GDP), state & local debt, IMF-sourced international annual general-government debt.
- **Coverage**: US (federal: GFDEBTN/GFDEGDQ188S/FGSDODNS; debt held by public), Japan (GGGDTAJPA188N). State/local: **SLGSDHNO, SLGSDGBS, SLLGSD, W018RCQ027SBEA all 404** — no FRED state/local series confirmed this session.
- **Frequency & lag**: Quarterly (GFDEBTN, GFDEGDQ188S), annual (GGGDTAJPA188N). Latest obs: **2026-01-01 (2026-Q1)** for GFDEBTN/GFDEGDQ188S/FGSDODNS — very fresh.
- **Access (exact endpoint + working params)**: **HTTPS times out from this host; plain HTTP + curl UA works**:
  `requests.get('http://fred.stlouisfed.org/graph/fredgraph.csv?id=GFDEGDQ188S', headers={'User-Agent':'curl/8.5.0'}, timeout=20)` → plain CSV `observation_date,<SERIES>`.
- **License & cost**: Free, keyless.
- **Sample series** (seen 2026-08-19): `GFDEGDQ188S` 2026-01-01 = **122.59387** %GDP; `GFDEBTN` 2026-01-01 = **39,065,421** $mn; `FGSDODNS` 2026-01-01 = 34,472,927 $mn (fed debt held by public? verify semantics); `GGGDTAJPA188N` 2023-01-01 = 239.971 (%GDP, Japan — **stale, ends 2023**).
- **Verified**: ✅ 2026-08-19 — HTTP 200 + CSV parsed for the 4 working IDs.
- **Notes & pitfalls**: HTTP (not HTTPS) is mandatory from this host; keep the curl User-Agent. State & local debt: use US Census Annual Survey of State and Local Government Finances (annual, HTML/XLSX scrape — not verified this session) or BEA NIPA tables.

## IMF — Global Debt Database (GDD) via SDMX (annual, 190 countries)

- **What**: General government (S13) debt liabilities, % of GDP (`FL_S13_POGDP_PT`), 1950–**2024**, 190 countries.
- **Coverage**: USA, CHN, IND, JPN, GBR, DEU, FRA, ITA confirmed + ~180 more. Annual only.
- **Frequency & lag**: Annual; latest year **2024** (data vintage 2025-09-17 per XML header). Documented fallback / backfill source.
- **Access (exact endpoint + working params)**: `https://api.imf.org/external/sdmx/2.1/data/GDD/USA.FL_S13_POGDP_PT.A` (keyless; returns **structure-specific XML** regardless of Accept header — parse bare `<Obs TIME_PERIOD="…" OBS_VALUE="…"/>` tags with regex; `TIME_PERIOD`/`OBS_VALUE` attr lists zip positionally).
- **License & cost**: Free, keyless, no registration.
- **Sample series** (seen 2026-08-19, last obs 2024): USA **120.786** (n=75); GBR 101.289; DEU 63.888; ITA 135.326; FRA 113.108; JPN 236.660; CHN 88.327; IND 81.286.
- **Verified**: ✅ 2026-08-19 — HTTP 200, parsed for all 8 countries + EA19 area.
- **Notes & pitfalls**: `<Obs>` tags are unprefixed (not `ss:Obs`) — naive `ss:` regex finds nothing. Many country×sector cells (e.g. CHN/IND private) have `<Obs>` without `OBS_VALUE` = missing. www.imf.org datamapper is Akamai-blocked from this host; api.imf.org works.

## IMF — World Economic Outlook (WEO) GGXWDG_NGDP (annual, actuals to 2025)

- **What**: General government gross debt, % of GDP — WEO headline series (`GGXWDG_NGDP`); actuals through **2025** + WEO forecasts to **2031**.
- **Coverage**: All WEO countries incl. USA, CHN, IND, JPN, GBR, DEU, FRA, ITA.
- **Frequency & lag**: Annual; **2025 actuals already populated** (WEO vintage mid-2026). Fastest annual source for the latest complete year.
- **Access (exact endpoint + working params)**: `https://api.imf.org/external/sdmx/2.1/data/WEO/USA.GGXWDG_NGDP.A` — same keyless host + bare-Obs XML parsing as GDD.
- **License & cost**: Free, keyless.
- **Sample series** (seen 2026-08-19, last ACTUAL 2025): USA **123.886**; CHN 99.238; IND 84.075; JPN 206.525; GBR 102.316; DEU 62.930; FRA 115.992; ITA 137.088. Forecasts extend to 2031 (USA 142.113). Series lengths 31–52 obs.
- **Verified**: ✅ 2026-08-19 — HTTP 200, 8/8 countries parsed. (EA19 aggregate key returned 200 but empty — use EA country list or Eurostat for EA aggregate.)
- **Notes & pitfalls**: WEO mixes actuals + forecasts in one series — cut at current year for actuals. Values move with each WEO vintage (revisions).

## ONS UK — Public sector finances (API DECOMMISSIONED)

- **What/Intent**: UK public sector net debt (PSND ex Bank of England), monthly PSF release.
- **Status**: ❌ **`api.ons.gov.uk` was fully retired 2024-11-25** — every route returns: *"This API has been decommissioned… fully retired on 25/11/2024"*. Probed `/timeseries/{J5II,L6XJ,J5SS,J2PS,HF6M,J5OV,JIVZ}/dataset/{mret,nm,UKEA,MM23,mgs,mna}/data` (all 404) and `/dataset`, `/search` (decommissioned notice).
- **Working alternative (unverified scrape)**: ONS website Excel download from the monthly PSF bulletin page `https://www.ons.gov.uk/economy/governmentpublicsectorandtaxes/publicsectorfinance/bulletins/publicsectorfinancesuk/<month><year>` — the June 2026 URL pattern returned 404 this session; find the current edition via the PSF release calendar. UK quarterly government debt is also covered by **OECD PSD (GBR, 2025-Q4, verified above)** and BIS WS_TC (GBR 102.2 %GDP 2025-Q4) as interim feeds.
- **Verified**: ❌ 2026-08-19 — API dead; bulletin scrape not confirmed.
- **Notes & pitfalls**: Do NOT build against api.ons.gov.uk. If ONS xlsx scrape is needed, budget for the `/file?uid=…` link format and monthly URL guessing.

## ECB — Government Finance Statistics dataflow (GSD/GFS) — NOT available

- **What/Intent**: Quarterly euro area government debt via ECB SDMX (data-api.ecb.europa.eu).
- **Status**: ❌ `GSD` flow is absent from the live dataflow catalog (`/service/dataflow/ECB/all/latest` = 104 flows, zero matching GSD/GFS/GDD). Key-guess queries (`Q.I9/U2/I8.S13.S1.N.B.F.IK.Z5.Z.Z.EUR.F800`) → 404/400. Legacy host `sdw-wsrest.ecb.europa.eu` → connection failure from this host. `GFS` key probes → 400.
- **Working alternative**: **Eurostat gov_10dd_edpt1** (annual, verified above) is the primary EU card; BIS WS_TC covers DE/FR/IT quarterly; OECD PSD covers EU members quarterly.
- **Verified**: ❌ 2026-08-19 — flow absent, hosts dead/404.
- **Notes & pitfalls**: If quarterly EU Maastricht debt becomes mandatory, re-check whether Eurostat exposes it under a different table code (the EDP quarterly notification data exists in the Eurostat free database UI — just not via this API table) or via OECD PSD.

---

## Country × frequency matrix

Latest observation actually seen (2026-08-19), best available frequency per country:

| Country | Daily/monthly | Quarterly | Annual |
|---|---|---|---|
| US | ✅ Treasury debt-to-penny (2026-08-17, daily) | ✅ BIS 2025-Q4 (116.4 %GDP); FRED GFDEGDQ188S 2026-Q1 (122.6 %GDP); OECD PSD 2025-Q4 | ✅ IMF WEO 2025 (123.9); GDD 2024 (120.8) |
| Euro area (EA20) | — | ✅ BIS 2025-Q4; member states via OECD PSD | ✅ Eurostat 2025 (87.8 %GDP); WEO 2025 |
| Germany / France / Italy | — | ✅ BIS 2025-Q4 (63.4/116.0/137.1 %GDP) | ✅ Eurostat 2025; WEO 2025 |
| UK | ❌ ONS API dead | ✅ BIS 2025-Q4 (102.2 %GDP); OECD PSD 2025-Q4 | ✅ WEO 2025 (102.3); GDD 2024 (101.3) |
| Japan | — | ✅ BIS 2025-Q4 (194.5 %GDP); OECD PSD 2025-Q4 | ✅ WEO 2025 (206.5); GDD 2024 (236.7); FRED GGGDTAJPA188N ends 2023 (stale) |
| China | — | ✅ BIS 2025-Q4 (99.3 %GDP, 139,119.3bn CNY) | ✅ WEO 2025 (99.2); GDD 2024 (88.3) |
| India | ⚠️ CGA monthly exists but site SSL-blocked from this host | ✅ BIS 2025-Q4 (83.9 %GDP) | ✅ WEO 2025 (84.1); GDD 2024 (81.3) |
| US state & local | — | ❌ no FRED series found (404s) | ⚠️ Census annual survey (unverified scrape) |

## Gaps

- **UK monthly PSF**: ONS API decommissioned (2024-11-25); interim = BIS/OECD quarterly; monthly requires ONS bulletin xlsx scrape (URL pattern shifted, unverified).
- **Quarterly EU Maastricht aggregate via API**: Eurostat table serves annual only now; ECB GSD flow absent. OECD PSD quarterly is the workaround (dimension semantics need mapping).
- **US state & local government debt**: no verified machine-readable series (FRED candidates 404; Census = annual scrape).
- **India official monthly (CGA)**: `www.cga.nic.in` SSL handshake fails from this host; RBI DBIE requires registration. IMF/BIS quarterly+annual are the working feeds.
- **China official MoF**: no keyless API; scrape of mof.gov.cn monthly balance sheets is fragile (Chinese-language portal) — BIS/IMF only.
- **Japan quarterly official (BoJ Flow of Funds / QSA)**: not probed to completion this session (DBnomics BoJ search empty); BIS + OECD PSD cover Japan quarterly.
- **OECD PSD measure mapping**: `F12.LL` %GDP series return ratio-scale values that don't all match expected aggregates (USA 0.5) — resolve dimension tree before production.
- **EA19 aggregate in WEO SDMX**: returns empty; use Eurostat for the euro-area aggregate.
