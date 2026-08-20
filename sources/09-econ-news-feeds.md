# Sources 09 — Economic News Feeds (official RSS, wires, query feeds, GDELT)

News/press-flow layer for the debt-monitor: institution press releases (default-risk events, supervisory actions), market wires (credit-event headlines), and queryable news aggregators (crisis-signal mining). Probes run 2026-08-19 with single-file Python `requests` scripts (`~/probes/p09*.py`); "latest pub" = newest item date actually seen in the feed body.

Companion: dossier 10 (FI earnings calls / filings). Free-tier *news APIs* (Finnhub/FMP) — see dossier 07.

---

## Official institutions — RSS (keyless)

| Feed | URL | Status (2026-08-19) | Latest pub seen |
|---|---|---|---|
| **ECB press** | `https://www.ecb.europa.eu/rss/press.html` | ✅ 15 items | 2026-08-19 (Lagarde panel remarks) |
| **Federal Reserve (all press)** | `https://www.federalreserve.gov/feeds/press_all.xml` | ✅ 20 items | 2026-08-19 (FOMC minutes) |
| **Bank of England news** | `https://www.bankofengland.co.uk/rss/news` | ✅ 50 items | 2026-08-11 |
| **FSB (Financial Stability Board)** | `https://www.fsb.org/feed/` | ✅ 10 items | 2026-08-10 |
| **FDIC press releases** | `https://www.fdic.gov/rss.xml` | ✅ 10 items | 2026-07-31 |
| **EBA news** | `https://www.eba.europa.eu/rss.xml` | ⚠️ works but stale | 2024-06-28 — feed alive, low volume |
| IMF news RSS | `…/en/News/RSS?Language=ENG` | ❌ 403 (Akamai — same block as datamapper, dossier 01) | — |
| World Bank RSS | several paths | ❌ 404 (moved; no RSS found this session) | — |
| BIS press RSS | `www.bis.org/list/…/index.rss` | ❌ 404 (site restructure; the HTML list page still renders) | — |
| Eurostat news RSS | 2 paths tried | ❌ 404 | — |
| US Treasury press feed | `home.treasury.gov/news/press-releases/feed` | ❌ 404 | — |
| NY Fed press | RSS path | ❌ HTML shell (JS app, like HHDC — dossier 08) | — |
| ESRB | `esrb.europa.eu/rss/press.html` | ❌ 404 | — |

**Working set**: ECB + Fed + BoE + FSB + FDIC = the core supervisory/monetary press flow. IMF/WB/BIS/Eurostat press: fetch their HTML list pages (works via plain requests) or rely on Google News queries (below) with `site:` operators.

## Market wires & finance RSS (keyless)

| Feed | URL | Status | Latest pub seen |
|---|---|---|---|
| **CNBC economy** | `https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114` | ✅ 30 items | 2026-08-20 (same-day) |
| **MarketWatch top** | `https://feeds.content.dowjones.io/public/rss/mw_topstories` | ✅ 10 items | 2026-08-19 23:30 GMT |
| **Yahoo Finance per-ticker** | `https://feeds.finance.yahoo.com/rss/2.0/headline?s=JPM&region=US&lang=en-US` | ✅ 15 items | 2026-08-20 — one feed per FI ticker; free ticker-level news |
| Reuters business | `feeds.reuters.com/...` | ❌ dead (connection refused — feeds retired) | — |
| FT home | `https://www.ft.com/rss/home` | ✅ 9 items | 2026-08-19 — headlines only (paywalled bodies) |

## Google News RSS — queryable crisis-signal feed (keyless)

- **What**: full Google News search as RSS: any boolean-ish query with `site:`, language/geo params. 100 items per response.
- **Verified**: ✅ `https://news.google.com/rss/search?q=debt+crisis+bank&hl=en-US&gl=US&ceid=US:en` → 200, 100 items, latest 2026-08-17; `q="bank failure" OR "credit loss"` → 200, 100 items.
- **Use for**: per-country feeds (`q=China+local+government+debt`), per-institution (`q=Credit+Suisse+style+stress`), event classes (`"debt default"`, "bank run"). Replace the dead IMF/WB/BIS press feeds with `site:imf.org`, `site:worldbank.org`, `site:bis.org` queries.
- **Pitfalls**: item descriptions are HTML snippets; `source` tag names the outlet; refresh cadence is Google's crawl (minutes–hours); no historical depth (rolling window).

## GDELT DOC 2.0 API — global news article search + tone timelines (keyless)

- **What**: GDELT's article index: search global news by query, return article list (`artlist`), **volume timelines** (`timelinevol`), and tone-weighted timelines (`timelinevolinfo`) — quantifiable news-pressure series for crisis signals.
- **Access**: `https://api.gdeltproject.org/api/v2/doc/doc?query=(sovereign+debt+OR+bank+failure)&mode=artlist&maxrecords=5&format=json&timespan=3d` — keyless.
- **Verified**: ⚠️ endpoint reachable; **hard rate limit 1 request / 5 seconds** (both probes got HTTP 429 with explicit "limit requests to one every 5 seconds" body — self-throttle or get whitelisted via the contact in the 429 message). Not retried further this session to respect the limit; structure well-documented.
- **Use for**: converting news flow into *indicators* (article volume + avg tone per country/theme per day) — the only free global-news quant layer found.
- **Pitfalls**: rate limit; English-language bias; query syntax quirks (no wildcards).

## Free-tier news/earnings APIs (need key — see dossier 07)

- **Finnhub** `/v1/news?category=economy` → 401 without key (verified). Free tier: general/earnings news.
- **FMP** `/v3/earning_call_transcript/...` → 401 without key (verified). Free tier covers transcripts on the starter plan.
- These slot into the accounts guide (dossier 07) alongside FRED/DBIE.

## Recommended feed stack

1. **Institutional press** (daily poll): ECB, Fed, BoE, FSB, FDIC RSS — supervisory events, resolutions, emergency facilities.
2. **Wires** (hourly poll): CNBC economy + MarketWatch + Yahoo per-ticker for the FI universe (ticker list from dossier 10).
3. **Query layer** (hourly): Google News RSS queries per theme/country/institution (crisis lexicon: default, downgrades, bank run, NPL, forbearance...).
4. **Quant layer** (daily, throttled): GDELT timelines per theme → news-pressure indicators.
5. Store as `(timestamp, source, title, url, entities[], theme)` rows; LLM classification later flags debt-relevant items.

## Gaps

- IMF/WB/BIS/Eurostat/Treasury official RSS all moved/retired — substituted by Google News `site:` queries (less authoritative, acceptable for monitoring).
- Reuters feeds dead; Bloomberg/FT bodies paywalled (headlines OK).
- GDELT rate limit (5 s) forces serialized pulls — fine at our volume.
- No free *historical* news archive (GDELT caps at rolling window; archives are licensed).
