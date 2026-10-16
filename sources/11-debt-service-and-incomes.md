# Sources 11 — Debt-Service Inputs: Sector Interest Paid, Sector Incomes, Gov Revenue, Maturing Principal

Verification probes for the metrics layer (interest payments/income, total payments/income, debt/income for S.13/S.14_S15/S.11/S.12). Every endpoint below was probed live on **2026-10-16** with the scripts `scripts/probe11_*.py` (single-file Python, httpx). "Latest obs" = newest observation seen in a response body. Companion dossiers: 03 (private-debt stocks), 04 (DSR), 05 (GDP deflators).

## Eurostat — nasq_10_nf_tr / nasa_10_nf_tr (quarterly sector accounts, non-financial transactions) — the core add

- **What**: Non-financial transactions by institutional sector: **D.41 interest payable** (`direct=PAID`) for S.11/S.12/S.13/S.14_S15, **B6G** gross disposable income (households), **B2A3G** gross operating surplus + mixed income (S.11/S.12). One dataset = M1 numerator + income denominators for the whole EU.
- **Coverage (quarterly)**: 32 geos = EU27_2020, **EA21** (not EA20!), BE BG CZ DK DE EE IE EL ES FR HR IT CY LV LT LU HU MT NL AT PL PT RO SI SK FI SE + **IS, NO, UA**. Annual `nasa_10_nf_tr` adds **CH** (and NO annual backfill); JP/US/GB absent (geo zeroed → not ESA reporters).
- **Frequency & lag**: Quarterly; latest obs seen **2026-Q2** (probed 2026-10-16) → ≈ 3–4 month lag. History from 1999-Q1 (request `sinceTimePeriod`).
- **Access**: Same JSON-stat API as the `eurostat` collector; **all dimension values must be valid or the API silently zeroes them (HTTP 200, `values=0`)** — the round-1 trap. Working params: `freq=Q, unit=CP_MEUR|CP_MNAC, direct=PAID, na_item=D41|B6G|B2A3G, sector=..., geo=..., sinceTimePeriod=...`. Note `s_adj ∈ {NSA, SCA}` (pin **NSA**, level-consistent with annual sums). Multi-value params (lists) work. `gov_10a_main`-style filters are NOT needed client-side — server-side filtering works once the codes are right.
- **License/cost**: Free, keyless.
- **Sample series** (seen 2026-10-16, CP_MEUR, NSA): D41 payable EA21 2026-Q2 = **47,937→50,117** (HH); D41 payable DE S14_S15 2026-Q2 = 12,010; DE S12 = 78,223; B6G DE S14_S15 2026-Q2 = 750,597; B2A3G DE S14_S15 = 144,105.
- **Verified**: ✅ live 2026-10-16 (`scripts/probe11_eurostat*.py` rounds 1–3).
- **Notes/pitfalls**: (1) EA aggregate geo is **EA21** in sector accounts (EA20 is zeroed) — unlike `gov_10dd_edpt1` which still serves EA20. (2) Operating-surplus code is **B2A3G** (B2G_B3G zeroed). (3) Quarterly values are **flows, not annualized** — metrics layer must TTM (sum trailing 4 quarters); annualization rules differ from FRED/BEA SAAR. (4) `nasq_10_f_bs` (stocks) also works once pinned: needs `finpos=LIAB` + `unit=MIO_NAC|MIO_EUR|PC_GDP`, na_item F3/F4, live through 2026-Q2 — resolves OVERVIEW §5.1.

## Eurostat — gov_10a_main (annual gov revenue: the revenue-denominator variant)

- **What**: Total general government revenue (`na_item=TR`) — M1/M3 government denominator variant "payments-to-revenue".
- **Coverage**: EU + EFTA + candidates (EA20 geo valid here); annual.
- **Frequency & lag**: **Annual only** — `freq=Q` is zeroed (no quarterly gov revenue on the dissemination API; `gov_10q_ggna`/`gov_10q_edpt1` 404, `gov_10dd_edpt1` is annual-only — confirms dossier 02).
- **Access**: `.../data/gov_10a_main?na_item=TR&sector=S13&unit=MIO_NAC|PC_GDP&geo=...`.
- **Sample** (seen 2026-10-16): DE TR 2024 = 2,024,422 M€ (46.8 % GDP), 2025 = 2,140,194 (47.9) — 2025 already published.
- **Verified**: ✅ live 2026-10-16.
- **Notes**: Quarterly gov **interest** is covered by `nasq_10_nf_tr` S.13 D41; only revenue is annual.

## BIS — debt securities statistics bulk (WS_NA_SEC_DSS): maturing-principal proxy

- **What**: Debt securities issued by sector (REF_SECTOR S13/S11/S12 + subsectors) × **original/residual maturity**, stocks (STO=LE) and flows. Maturity codes decoded from TITLE: `S` = original ≤1y; `L` = original >1y; **`LS` = original >1y with residual ≤1y** (long-term now near maturity); `Y12/Y25/Y5A/YA_` = original-maturity buckets (>1–2y / >2–5y / >5–10y / >10y); `T` = all.
- **Proxy rule**: securities maturing within 1 year = stocks(`S`) + stocks(`LS`).
- **Coverage**: 60 REF_AREA (incl. US, JP, GB, CN, IN, U2 aggregate; AR to ZA). S+LS quarterly stocks: 37 issuers incl. EA members, GB, JP, BR, MX, TR, ZA, U2 — **US is absent from `LS`** (US rows only S/L/T → US proxy = `S` only, understates; documented).
- **Frequency & lag**: Quarterly; latest obs seen **2026-Q1** (DE S13 LS EUR M 2026-Q1 = 261.5 bn; S = 2.3 bn — multiple counterpart/valuation rows per cell, dedupe needed).
- **Access**: `https://data.bis.org/static/bulk/WS_NA_SEC_DSS_csv_col.zip` (21 MB zip → 200 MB CSV, 146k series × 470 period cols). **Not `WS_SDE`** (404) — the flow name on the DSS topic page is `WS_NA_SEC_DSS`. CSV has mixed int/float period columns — read with `infer_schema_length=0`.
- **License/cost**: Free, keyless (BIS terms, attribution).
- **Verified**: ✅ live 2026-10-16 (`scripts/probe11_bis_sde.py` + follow-ups).
- **Notes/pitfalls**: Units are **currency codes** (USD, EUR, national), not XDC/770; per-country national-currency rows coexist with USD/EUR rows under different counterpart-area combos — collector must pre-filter rows (146k rows melt to millions otherwise): keep REF_SECTOR ∈ {S13,S11,S12}, FREQ=Q, STO=LE, ACCOUNTING_ENTRY=L, MATURITY ∈ {S,LS,T}, CURRENCY_DENOM=_T, CUST_BREAKDOWN=_T; prefer the row whose UNIT_MEASURE is the country's own currency, valuation M (N fallback), and dedupe on counterpart combos. UNIT_MULT 9 = billions.

## United States — FRED API + DBnomics Fed Z.1 mirror (income + interest paid)

- **What**: HH disposable income, HH interest payments, federal + state/local gov interest payments, NFC gross value added; Z.1 quarterly interest-paid for households (S14+S15), NFC, and **general government S13** (computed series, sums federal+S&L).
- **Pinned series** (all live, obs seen 2026-10-16):

| Series | What | Freq | Latest obs |
|---|---|---|---|
| `DPI` | Disposable personal income (SAAR) | Quarterly | 2026-Q2 = 23,965.585 $bn |
| `B069RC1Q027SBEA` | Personal interest payments (SAAR) | Quarterly | 2026-Q2 |
| `A091RC1Q027SBEA` | Federal gov interest payments (SAAR) | Quarterly | 2026-Q2 = 1,279.7 $bn |
| `Y705RC1Q027SBEA` | State & local gov interest payments (SAAR) | Quarterly | 2026-Q2 |
| `A455RC1Q027SBEA` | Gross value added, NFC (income proxy) | Quarterly | 2026-Q2 |
| `FED/Z1 FA156130005.Q` | HH interest paid (IMA, computed, SAAR) | Quarterly | 2026-Q2 = 2,019,813 $mn |
| `FED/Z1 FA106130001.Q` / `FA106130003.Q` | NFC interest paid (IMA input / zero-seasonal) | Quarterly | 2026-Q2 |
| `FED/Z1 FA366130005.Q` | General government (S13) interest paid (computed) | Quarterly | mirror carries it (FRED `BOGZ1FA366130005Q` too) |

- **Verified**: ✅ live 2026-10-16 (`scripts/probe11_fred_dbnomics*.py`). FRED search API is rate-limited from this host — collectors fetch by pinned ID (no search at runtime). Old BEA IDs (`A067RC1Q027SBEA` etc.) now HTTP 400; FRED's Z.1 `BOGZ1FL…` mirror is empty/dead — **use the DBnomics `FED/Z1` mirror (indexed 2026-09-30)**.
- **Notes/pitfalls**: BEA/FRED flows are **SAAR (annualized)** — use as-is, no TTM summing (contrast Eurostat). NFC "income": no clean GOS level on FRED; GVA (`A455RC`) is the documented proxy (broader than B2A3G). `FA106130001.Q` shows repeated flat values in the mirror — collect `FA106130003.Q` alongside and cross-check at validation.

## United Kingdom — ONS via DBnomics mirror (ONS/UKEA, ONS/PUSF)

- **What**: UK Economic Accounts quarterly sector accounts: HH gross disposable income, D.41 interest paid by sector, corporate gross operating surplus; PUSF public-sector finances detail.
- **Pinned series** (mirror `indexed_at` 2026-10-01 — fresh):

| Series | What |
|---|---|
| `HABN.Q` | Households (S.14) gross disposable income B.6g, CP £m NSA (level) |
| `HAAJ.Q` | NPISH (S.15) B.6g level (sum with HABN for S14_S15) |
| `HACY.Q` | Households (S.14) Interest (D.41) uses £m NSA |
| `AE7P.Q` | HH total interest before FISIM (alt) |
| `EABG.Q` | NFC (S.11) Interest (D.41) uses £m (2026-Q2 = £13,397 m) |
| `I69W.Q` / `I69X.Q` | Central / local gov total interest paid excl. FISIM (2026-Q2 CG = £33,125 m) |
| `CGBZ.Q` / `CGBY.Q` | Gross operating surplus of corporations, SA / NSA |
| `PUSF ANLO.Q` | PS current exp: interest & dividends paid (monthly alt) |

- **Verified**: ✅ live 2026-10-16 (values above read from the mirror).
- **Notes/pitfalls**: ONS direct APIs are dead-for-automation: beta `api.beta.ons.gov.uk` has no `/v1|/v2/datasets` route (404, "No API is defined"); the old XMDB is decommissioned (dossier 02). The DBnomics `ONS` provider (46 datasets) is the machine path. UKEA quarterly flows are **not annualized** → TTM.

## Global annual government — OECD National Accounts (DBnomics mirror)

- **What**: Annual general-government **interest expenditure** (D.41) and **total revenue** in national currency, from OECD National Accounts at a Glance table 12.
- **Series grammar**: `OECD/DSD_NASEC10@DF_TABLE12_EXP/A.{COUNTRY}.S13._Z.D.D41._Z._Z.XDC.S.V.N.T0200` (interest) and `OECD/DSD_NASEC10@DF_TABLE12/A.{COUNTRY}.S13._Z.C.OTR._Z._Z.XDC.S.V.N.T0200` (total revenue). Subsectors S1311–S1314 also available.
- **Coverage**: OECD+ (~60–90 countries incl. JPN, KOR, AUS, CAN, MEX, CHL, COL…); mirror indexed 2026-06-16 → data through ~2024–2025.
- **Sample** (seen 2026-10-16): JP general-gov interest 2024 = **¥7,780,600 m** (2023 = 7,403,200) — plausible vs ~¥1,060tn debt.
- **Verified**: ✅ live 2026-10-16.
- **Notes/pitfalls**: The mirror's `DF_QNA_INC_SAV` serves only **total-economy (S1)** rows — no household-sector disposable income on the mirror (searched: 0 hits). OECD direct SDMX (`sdmx.oecd.org/public/rest/v2`) returned HTTP 400 to dataflow listing this session — mirror-only for now.

## World Bank — WDI government revenue (central-gov fallback)

- **What**: `GC.REV.XGRT.GD.ZS` — central government revenue incl. grants, % GDP, ~150 economies, annual (DE 2024 = 29.4 — note: **central, not general government**; use only as documented fallback).
- **Verified**: ✅ live 2026-10-16 (DEU/CHN/USA values seen). **`GC.INTP.TOTL.GD.ZS` (interest) returns zero observations — WDI has no gov interest.**

## Negative results (probed 2026-10-16, do not retry blindly)

| Candidate | Result |
|---|---|
| IMF SDMX `GFS_BS` (109 ctys) | Balance-**sheet** stocks only (F1–F6, net worth) — no operations statement |
| IMF SDMX `GFS_SOEF` / `GFS_SFCP` | Other-economic-flows / cash statements — no interest/revenue detail |
| IMF SDMX `QGFS` (57 ctys, Q+M+A) | Stocks by account type (`SOO`) — no interest |
| IMF WEO (145 indicators enumerated) | No interest variable (GGX*, GGXWD*, BCA…) |
| WDI `GC.INTP.*` | Zero observations |
| ONS beta API v1/v2 `/datasets` | 404 — no API defined |
| ESRI Japan SNA landing (`/en/sna/data/sna_kakuhou_e.html`) | 404 — moved; JP income rides on OECD T12 (gov) only |
| BIS `WS_SDE_csv_col.zip` | 404 — correct flow is `WS_NA_SEC_DSS` |
| FRED Z.1 mirror (`BOGZ1FL*`) | Empty/dead observations — use DBnomics `FED/Z1` |
| OECD mirror `DF_QNA_INC_SAV` households | No S14/S1M sector rows |

**Consequence**: government *interest* is available for EU (+IS/NO/UA quarterly; CH annual), US, UK (quarterly) and OECD+ (annual) — **no global open source beyond ~90 countries**. Household/NFC incomes outside EU/US/UK are a documented gap (M1/M3); M2 rides on BIS DSR (32 ctys) regardless.

## Country × metric feasibility matrix (post-probe)

| Block | Gov M1 (int/income) | Gov M3 (debt/GDP, debt/rev) | Private M1 | M2 | Private M3 |
|---|---|---|---|---|---|
| EU-27 + EA21/EU27 | quarterly (nasq D41 × GDP/rev) | quarterly %GDP / annual rev | quarterly all sectors | BIS DSR + gov S+LS proxy | quarterly (BIS stock ÷ TTM income) |
| IS, NO, UA | quarterly | quarterly / annual rev | quarterly | BIS DSR (NO) | quarterly |
| CH | annual (nasa) | quarterly (BIS) / annual rev | annual | — | annual |
| US | quarterly (Z.1 S13 / A091+Y705) | quarterly / annual rev (OECD T12) | quarterly (FRED+Z.1) | BIS DSR + S-only proxy | quarterly |
| UK | quarterly (I69W+I69X) | quarterly / annual rev | quarterly (UKEA) | BIS DSR + S+LS proxy | quarterly |
| JP | annual (OECD T12) | quarterly (BIS) / annual rev | **gap** (no HH income) | BIS DSR + S+LS proxy | **gap** |
| OECD non-EU (~30) | annual (OECD T12) | annual | gap | BIS DSR where present | gap |
| CN, IN + rest | **gap** | annual (GDD/WEO debt %GDP; WDI rev) | gap | BIS DSR private-only (CN/IN) | gap |
