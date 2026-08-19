# Sources — Verified Data-Source Dossiers

Research phase deliverable for the debt-monitor project: **what data exists, where, at what frequency, and whether it actually works** — every source probed live (HTTP status + real latest observation) on **2026-08-19**. Cadence rule applied throughout: **monthly+ preferred, quarterly accepted, annual only as documented fallback**.

## Dossiers

| File | Domain | Cards | Verified live |
|---|---|---|---|
| [01-aggregators.md](01-aggregators.md) | Cross-country aggregators: BIS, IMF (GDD/WEO), World Bank, OECD, DBnomics, FRED-as-aggregator | 9 | 8 |
| [02-government-debt.md](02-government-debt.md) | Government debt stocks (central/state/local): US, EA/EU, UK, JP, CN, IN | 9 | 7 |
| [03-private-debt.md](03-private-debt.md) | Private debt stocks: household (mortgages, consumer) + NFC (loans, bonds) | 11 | 6 |
| [04-debt-health.md](04-debt-health.md) | Debt health: delinquency, NPL, DSR, charge-offs (banks & households) | 9 | 6 |
| [05-deflators-gdp.md](05-deflators-gdp.md) | CPI/HICP monthly + nominal GDP quarterly (deflation & normalization) | 10 | 9 |
| [06-yields.md](06-yields.md) | Government yield curves + corporate IG/HY yields + lending rates | 15 | 11 |
| [07-accounts-guide.md](07-accounts-guide.md) | Account setup: FRED key, RBI DBIE, what to skip | 6 | — |
| [08-js-gated-sources.md](08-js-gated-sources.md) | JS-gated sources: value/effort analysis + verdicts | 5 | — |

Each dossier follows the same card format — **What / Coverage / Frequency & lag / Access (exact working endpoint) / License & cost / Sample series (ID, latest obs date + value) / Verified (result) / Notes & pitfalls** — and closes with a country × frequency matrix and an honest Gaps section. Failed/blocked sources are documented with evidence (that's what the ❌/⚠️ cards are for) so we never re-litigate them.

## The verified backbone (one glance)

- **Volumes**: BIS Total Credit bulk (quarterly, 48 countries, gov+HH+NFC, %GDP) · IMF GDD/WEO annual breadth (190/207 countries) · US Z.1/H.8 (quarterly/weekly) · ECB BSI/QSA (monthly/quarterly, EA+members)
- **Health**: BIS DSR (quarterly, 32 countries) · IMF FSI quarterly NPL (~100 countries incl. CN/IN) · FRED US delinquency/charge-off (quarterly) · ECB SUP NPE (quarterly, EA)
- **Deflators/normalizers**: FRED CPIAUCSL/GDP (monthly/quarterly, US) · ECB ICP + Eurostat HICP (monthly, EA) · IMF IFS via DBnomics (monthly CPI + quarterly GDP, GB/JP/CN/IN)
- **Yields**: US Treasury daily CSV · ECB YC daily (U2) · Japan MoF daily · BoE GLC daily · ICE BofA IG/HY + EUR OAS daily via FRED

## Environment quirks (verified, plan around them)

1. `fred.stlouisfed.org` **HTTPS times out from this host** — plain HTTP + curl User-Agent works; for Fed data prefer the DBnomics `FED/` mirror.
2. BIS bulk lives at **`data.bis.org/static/bulk/…`** (www.bis.org paths 404; stats.bis.org serves an HTML shell on bulk paths).
3. IMF: use **`api.imf.org/external/sdmx/2.1`** (datamapper is Akamai-403 from here).
4. ONS API is **decommissioned** (2024-11-25); NY Fed HHDC, BoE IADB/MLAR, EBA dashboard, ChinaBond, FBIL/CCIL, RBI DBIE are all **gated for anonymous scripts** — see the Gaps sections.

Acquired datasets (first pipeline outputs): [../data/](../data) — `wb_npl_annual.csv` (154 economies, 2000–2025), `imf_fsi_npl.csv` (152 countries, quarterly where reported) via [../scripts/acquire_npl.py](../scripts/acquire_npl.py).

Synthesis and recommended pipeline: [../OVERVIEW.md](../OVERVIEW.md).
