# Sources 10 — Financial-Institution Earnings Calls & Regulatory Filings

Quarterly disclosures of banks, hedge funds, private equity firms: earnings-call transcripts/recordings, earnings 8-Ks, 10-Q/10-K, 13F/13D holdings. The credit-quality narrative (provisions, charge-offs, NPLs, reserve builds) is disclosed here *before* it appears in aggregate statistics — a genuine leading channel for crisis detection. Probes run 2026-08-19 (`~/probes/p10*.py`).

## SEC EDGAR — the backbone (free, keyless, with UA quirks)

**CRITICAL access note (verified this host)**: EDGAR rejects short/custom User-Agents with **403**. A **full Chrome UA string** gets 200 on `data.sec.gov` (both HTTP and HTTPS):
`User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36`. Additionally, `www.sec.gov/Archives/...` document fetches 403 from **this datacenter host** (host-level block; full browser headers don't help) — `data.sec.gov` APIs work fine. Production should run collectors from a residential/cloud egress that isn't flagged, or proxy those fetches. The JSON APIs below are the working core.

### EDGAR submissions index (`data.sec.gov/submissions`)

- **What**: per-company filing history (form, date, accession, primary doc) — everything needed to discover 8-K/10-Q/13F on schedule.
- **Verified**: ✅ `https://data.sec.gov/submissions/CIK0000019617.json` → 200, JPMorgan: 25,746 recent filings; latest 8-K 2026-07-23 (earnings, item 2.02); 26 8-Ks in the recent window.
- **Access**: `data.sec.gov/submissions/CIK{10-digit}.json`; rate limit 10 req/s with the Chrome-UA rule above.
- **Notes**: `filings.recent` arrays are parallel; older filings paginate in `filings.files[].name`. CIK resolution: `https://www.sec.gov/files/company_tickers.json` (403 from this host — mirrored builds of it exist, or use FTS `display_names`).

### EDGAR full-text search (FTS) — `efts.sec.gov/LATEST/search-index`

- **What**: Elasticsearch over every EDGAR filing since 2001: query + form filter + date range. **The discovery engine for earnings material.**
- **Verified**: ✅ 200 with hits; e.g. `q="provision for credit losses"&forms=8-K&startdt=2026-07-01&enddt=2026-08-19` → **681 filings**, each hit carrying: `adsh`, `ciks`, `display_names` (ticker!), `file_date`, `items` (e.g. `["2.02","9.01"]` = earnings + exhibits), `file_type` (`EX-99.1` = the press release), `sics` (industry code — filter banks `6021/6022`), `biz_locations`.
- **Access**: `https://efts.sec.gov/LATEST/search-index?q=…&forms=8-K&startdt=…&enddt=…` (needs the Chrome UA too).
- **Use**: `items=2.02` + `file_type=EX-99.1` = machine-findable earnings releases; `sics` filter builds the FI universe without a ticker file; phrase queries on credit-quality language ("provision for credit losses", "net charge-offs") find deteriorating lenders early.
- **Notes**: `_id` = `adsh:filename` (builds the archive URL); date params are `startdt/enddt` (my earlier `dateRange` guess did nothing — hits ran back to 2004).

### EDGAR XBRL company facts — structured numbers

- **What**: every XBRL-tagged fact in filings: provisions, charge-offs, loan balances, allowances — as **data**, no transcript needed.
- **Verified**: ✅ `https://data.sec.gov/api/xbrl/companyfacts/CIK0000019617.json` → 200, **4.57 MB** of structured facts for JPM alone.
- **Use**: quarterly provision/charge-off series per FI straight from 10-Q/10-K XBRL — pairs with dossier 04's aggregate delinquency data.

### What's blocked from this host (documented, not fatal)

- `www.sec.gov/Archives/...` documents (the actual 8-K exhibit HTML): 403 from this datacenter IP. Fix: different egress in production, or the FTS metadata + XBRL facts (which suffice for indicator building). Atom feeds (`cgi-bin/browse-edgar...output=atom`) also 403 here.

## Earnings-call transcripts

| Route | Status | Notes |
|---|---|---|
| **Motley Fool** `fool.com/earnings/call-transcripts/` | ❌ 404 JS shell (Next.js app) | Free for humans in browser; scripted index gone |
| **FMP** `earning_call_transcript/{ticker}` | 401 without key | Free/starter tier covers transcripts — **the pragmatic route**; key signup in dossier 07 |
| **Finnhub** `/stock/earnings-calls` | 401 without key | Free tier; audio + some transcripts |
| **API-Ninjas** earnings transcript | 400 Missing API Key | Free tier exists |
| Seeking Alpha / Bloomberg | paywalled | Out of scope |
| **DIY from webcasts**: 8-K item 2.02 → investor-relations page → webcast/recording | manual | Companies post replays; ASR (whisper) can transcribe — build cost, no license issues for internal use |

**Recommendation**: FMP free key (dossier 07) for transcripts of the top ~50 FIs + EDGAR FTS/XBRL for everything else. Hedge funds/PE don't do earnings calls (no public ticker) — their channel is **13F/13D/ADV** filings (EDGAR covers 13F/13D; ADV via IAPD is keyless) + their LP-letter commentary (not open data).

## Non-US FIs

- **UK**: RNS announcements (London Stock Exchange) — company news including results; `www.londonstockexchange.com/news` is JS-gated (same pattern as dossier 08); regulatory primary info on the National Storage Mechanism requires interaction. FCA primary-market disclosures keyless-ish but HTML.
- **EU**: no unified free results feed; issuer disclosures live on national OAMs (each JS-heavy). ECB SUP (dossier 04) already covers EU bank health keylessly at the aggregate.
- **Japan**: EDINET (Japanese/English) — filing search keyless; xbrl data files available; JPX announcement tditoki system JS-gated. TSE TDnet transcripts not public (only summaries).
- **Priority call**: US EDGAR first (richest + verified), EU/UK via aggregates + news layer (dossier 09), JP optional.

## 13F / 13D holdings (hedge funds)

- Covered by the same EDGAR APIs above: submissions JSON lists 13F-HR quarterly; FTS finds 13D/13G by issuer name. Verified reachable via `data.sec.gov` from this host.
- Value for crisis detection: positioning concentration, crowded trades (e.g. svb-style duration exposure via 13F bond holdings).

## Gaps

- Transcripts: no keyless route verified (FMP/Finnhub keys needed; Motley Fool JS-gated; DIY ASR = build effort).
- Non-US results feeds: all JS-gated portals — defer, use dossier 09 news layer as substitute.
- `www.sec.gov` document bodies host-blocked here — production must solve egress (proxy or different host).
- No free historical transcript archive (licensed products only).
