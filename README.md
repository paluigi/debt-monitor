# Debt Monitor — collection pipeline

Scheduled collection of debt-volume, debt-health, deflator/GDP and yield data
into MongoDB, plus an economic-news and FI-earnings layer. Source selection,
endpoints and host quirks are documented in the verified dossiers under
[sources/](sources/) — every collector cites them.

## Quickstart

```bash
# 1. MongoDB (local, persistent across reboots via named volume)
docker run -d --name debt-monitor-mongo --restart unless-stopped \
  -p 27017:27017 -v debt-monitor-mongo-data:/data/db mongo:7

# 2. Environment
cp .env.example .env      # then fill in FRED_API_KEY etc.
uv sync                   # creates .venv and installs dependencies

# 3. Run
uv run debt-monitor list                  # registered collectors
uv run debt-monitor collect               # one-shot run of everything
uv run debt-monitor collect us_treasury   # single source
uv run debt-monitor metrics --export      # derived metrics + data/metrics/metrics.csv
uv run debt-monitor coverage              # metrics coverage summary
uv run debt-monitor schedule              # daily scheduler (foreground)
```

Configuration (see `.env.example`): `MONGO_URI` (defaults to
`mongodb://localhost:27017`), `MONGO_DB_NAME`, `FRED_API_KEY`, `FMP_API_KEY`,
`FINNHUB_API_KEY`, and the schedule (`SCHEDULE_HOUR`/`SCHEDULE_MINUTE`/
`SCHEDULE_TZ`, default 06:00 Europe/Rome, plus APScheduler `jitter=900`).
The scheduler recomputes derived metrics at HH:45 after the collection run.

Retries: every HTTP call is wrapped with tenacity (`wait_exponential_jitter`,
4 attempts); a failing collector is retried once more at the collector level
and never blocks the others. Every run is logged to the `_runs` collection.

## Collections (one per source)

| Collection | Source | Content |
|---|---|---|
| `bis` | BIS bulk zips | Total credit stocks (gov/HH/NFC/private) + debt-service ratios + debt securities by residual maturity, quarterly |
| `imf` | IMF SDMX | GDD sector debt %GDP + WEO gov debt %GDP/level + nominal GDP, annual |
| `fred` | FRED API | US CPI/GDP/federal debt, yields, ICE BofA spreads, delinquency/charge-offs, mortgage rate, DPI + interest payments (dossier 11) |
| `ecb` | ECB data-api | BSI MFI loans (monthly), QSA sector stocks, MIR lending rates, gov yield curves (daily), HICP via the new `HICP` flow (ECOICOP v2) |
| `eurostat` | Eurostat API | HICP monthly + EDP Maastricht debt + sector accounts (D.41 interest payable, B6G/B2A3G incomes) + quarterly GDP + gov revenue (dossier 11) |
| `us_treasury` | FiscalData + Treasury CSV | Debt-to-the-penny (daily) + daily par yield curve |
| `dbnomics` | DBnomics mirrors | Fed Z.1/H.8 (stocks + interest paid), IMF IFS CPI+GDP, ECB SUP NPE, IMF FSI NPL, ONS UKEA (UK sector accounts), OECD T12 gov interest/revenue (dossier 11) |
| `worldbank` | World Bank API | NPL ratio + central-gov revenue %GDP, annual, ~200 economies |
| `nyfed` | NY Fed HHDC | Household Debt & Credit report XLSX, quarterly (URL rolls to `HHD_C_Report_{YYYY}Q{n}`) |
| `boe` | Bank of England | Nominal gilt spot curve, daily |
| `japan_mof` | Japan MoF | JGB yield curve, daily |
| `news` | RSS/GDELT/Finnhub | Economic news articles, deduped by URL |
| `fi_filings` | EDGAR FTS + FMP | Earnings-related 8-Ks + FI earnings-call transcripts |
| `metrics` | derived | Debt-burden metrics computed from the collections above (see below) |
| `_runs` | internal | Per-collector run log (status, doc counts, errors) |

Quantitative records share one schema: `_id` = sha256(source\|dataset\|series\|
country\|period\|dims), so re-runs upsert idempotently. NY Fed sheets are
archived as raw rows tagged with `report_quarter`.

## Derived metrics (`metrics` collection)

Per actor × country × period, computed from the collections above (sources and
conventions in [sources/11-debt-service-and-incomes.md](sources/11-debt-service-and-incomes.md);
`src/debt_monitor/metrics.py` for the implementation):

- **interest_to_income** — sector interest payable (D.41) ÷ income. Actors:
  households (income = gross disposable income), non-financial corporations
  (gross operating surplus; gross value added for the US), financial
  corporations, government (denominators: GDP **and** general-government
  revenue).
- **debt_service_to_income** — households/NFC: BIS DSR as published (interest +
  amortisation). Government: (interest + debt securities maturing ≤ 1 year,
  BIS WS_NA_SEC_DSS `S`+`LS`) ÷ GDP — a securities-only rollover-risk proxy
  (the US has no `LS` split, so its proxy understates).
- **debt_to_income** — end-of-period debt stock (BIS total credit; WEO for the
  annual global tier) ÷ trailing income; government gets both `gdp` and
  `government_revenue` denominators.

Every metric doc carries full component provenance (numerator/denominator
source, series, value, scale) and `method="observed"` — no estimates; gaps are
documented in the dossier's feasibility matrix (notably: no open source for
government interest outside EU/US/UK/OECD; no household income for Japan,
China, India). Conventions: Eurostat/ONS quarterly flows are trailing-4-quarter
sums; FRED/BEA SAAR values are used as annual rates; annual-only inputs produce
annual rows only.

## Deliberately excluded

- **RBI DBIE** — registration geoblocked outside India (revisit if access changes).
- ECB ICP mirror (frozen 2025-12 with the ECOICOP v1→v2 break) — replaced by
  the portal's new `HICP` flow (keys `M.{area}.N.000000.4D0.{ANR,INX}`) and by
  Eurostat `prc_hicp_minr` in the `eurostat` collector. ONS API
  (decommissioned) and JS-gated portals (BoE IADB, EBA dashboard, ChinaBond)
  remain excluded — see dossier 08 verdicts.
- ECB QSA (EA sector-account stocks) is currently WAF-blocked at the ECB data
  portal for this network (HTTP 400 "access blocked" for every UA/client while
  BSI/MIR/YC work). The keys stay in the daily rotation and will resume
  automatically if the block lifts; BIS WS_TC covers EA sector stocks meanwhile.

## Repo layout

- `src/debt_monitor/` — the pipeline (collectors, metrics layer, scheduler, CLI)
- `sources/` — data-source research dossiers driving every endpoint choice
- `scripts/` — one-off research harvests and dossier-11 probe scripts
  (`acquire_npl.py`, `probe11_*.py`; the NPL logic now lives in the
  `dbnomics`/`worldbank` collectors)
- `data/` — committed CSV exports (`data/metrics/metrics.csv` via
  `debt-monitor metrics --export`)
