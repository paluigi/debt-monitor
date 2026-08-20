# Sources 08 — JS-Gated Sources: What They Contain & Whether They're Worth Acquiring

Four sources sit behind JavaScript apps that return empty HTML shells to plain HTTP clients (verified 2026-08-19, dossiers 03/04/06). This dossier gives the decision inputs: **what you'd actually get, what already covers it keylessly, realistic acquisition effort, and a recommendation**. Note: live browser-based probing was not possible from this research host (no Chromium); effort estimates rest on the documented JS behavior of each portal plus the structure of their public pages.

Acquisition options, in increasing effort:
- **(a) Manual download** — human clicks once per release; file lands in a watched folder. ~5 min/quarter/source.
- **(b) JS-capable fetch** — Playwright/Browser-Use session renders the page, captures the XHR/file URL, then a plain HTTP client downloads it. Build: ~2–4 h/source; run: minutes.
- **(c) Vendor/wrapper library** — akshare/TuShare etc. (fragile, ToS-grey, maintenance burden).

---

## 1. NY Fed — Household Debt & Credit Report (HHDC)

- **Blocked how**: landing page is a JS app (`{{data_url}}` templates, `cmd-main.js`); every `medialibrary/…/data/xls/*.xlsx` URL soft-404s to a generic page (byte-identical to a bogus filename's response — differential-probe verified, dossier 03).
- **What you'd get (unique value)**: the richest *household* debt dataset public anywhere: quarterly stocks AND delinquency/90+ transition rates **per product** — mortgage, HELOC, auto, student, credit card — plus auto origination volumes by credit score, from Equifax microdata (~5.2bn obs). The student/auto delinquency split exists nowhere else keylessly. US only.
- **Already covered keylessly**: total HH stocks (Z.1 FL153165105/FL153166000), bank-level delinquency (FRED DRCCLACBS etc., dossier 04). NOT covered: student-loan and auto 90+ delinquency detail, per-product transition rates, origination-quality bins.
- **Crisis-detection value**: HIGH — 2008-style stress first shows in student/auto/card delinquency transition rates, 2–4 quarters before charge-offs. The NY Fed series are the canonical "early" US household stress signal.
- **Effort**: LOW-MEDIUM. The report XLSX is a stable quarterly artifact; option (a) manual = 5 min/quarter; option (b) = one Playwright session to capture the medialibrary URL pattern (they rotate per quarter but follow `household-debt-and-credit-report-{Q}{YYYY}-xlsx` style).
- **Recommendation**: **YES — acquire.** Start manual (a) now; automate (b) later if the dashboard needs it. It's the single best household-health dataset in the world and it's free.

## 2. Bank of England — IADB (monthly Lending to Individuals) + MLAR arrears

- **Blocked how**: the IADB "Database" pages return a 17 KB JS app shell with zero series content; `CSVf=TN/TX` params ignored; no DBnomics mirror (BOE provider has 26 datasets, none IADB — verified, dossier 03). MLAR not mirrored either (dossier 04).
- **What you'd get (unique value)**: UK monthly secured (mortgage) + unsecured (consumer) lending stocks & flows — the UK counterpart of ECB BSI monthly; MLAR adds quarterly mortgage arrears/possession counts (UK household health).
- **Already covered keylessly**: UK HH/NFC quarterly stocks via BIS WS_TC (2025-Q4, dossier 03); UK NPL via IMF FSI (2025-Q1) + WB annual; DSR via BIS (2025-Q4).
- **Crisis-detection value**: MEDIUM — fills the UK monthly-credit gap; arrears are a good household-stress gauge. But quarterly BIS + FSI already give the trend.
- **Effort**: MEDIUM. Option (b) requires capturing the IADB XHR (`boeapps/database` endpoints render via JS); MLAR is a quarterly xlsx from the Bankstats releases — closer to (a). BoE also publishes most series as CSV on release pages (URL pattern `/boe-files/...` rotates monthly).
- **Recommendation**: **DEFER.** Take BIS quarterly for now; revisit if UK monthly momentum becomes analytically important. If acquired, do (a) monthly for IADB totals only.

## 3. EBA — Risk Dashboard (EU banks)

- **Blocked how**: landing page 404s to a 10.5 KB JS shell; xlsx/zip URLs generated client-side and rotate per quarter (verified, dossier 04).
- **What you'd get (unique value)**: EU-wide bank NPL ratio **by country and portfolio**, stage-2 loans (IFRS 9), forbearance, coverage — the stage-2/forbearance detail is unique.
- **Already covered keylessly**: ECB SUP NPE stocks by country via DBnomics `ECB/SUP` (2026-Q1, dossier 04) — same supervisory universe, stock levels; NPL ratio computable or IMF FSI per country.
- **Crisis-detection value**: MEDIUM — stage-2 ("underperforming but not NPL") is the genuine leading edge; NPL stocks are lagging.
- **Effort**: LOW-MEDIUM. One xlsx per quarter; URLs rotate but the `document_library/Publications/Risk_analysis/Risk_Dashboard/` path is stable — option (a) manual = 5 min/quarter; (b) = resolve URL once per quarter with a headless browser or by parsing the publications JSON if present.
- **Recommendation**: **MAYBE — cheap to add manually.** If stage-2 matters to the model, grab it manually quarterly; otherwise ECB SUP covers EU bank health keylessly.

## 4. ChinaBond / chinamoney — daily CGB yield curve (+ FBIL for India)

- **Blocked how**: portals render client-side; known POST endpoints 404; chinamoney API path 404 (verified, dossier 06). India FBIL renders data client-side; CCIL 403; no FRED/DBnomics fallback (IRLTLT01CN/IN 404; OECD mirrors stale).
- **What you'd get (unique value)**: China daily sovereign curve (CGB) and India daily G-sec benchmark — closing the last two daily-yield gaps for the countries in scope.
- **Already covered keylessly**: nothing at daily frequency for CN/IN sovereign yields. (BIS/IMF don't carry them; yfinance bond ETFs absent/illiquid for CN/IN.)
- **Crisis-detection value**: MEDIUM-HIGH — sovereign-curve dynamics (steepening/inversion, level shifts) are core stress signals; CN/IN are the two biggest emerging markets.
- **Effort**: HIGH. Options: (c) akshare wraps ChinaBond but breaks whenever the portal changes (high maintenance); headless scraping of FBIL/ChinaBond = (b) with anti-bot risk; licensed vendors = money. RBI DBIE registration (free, dossier 07) covers **India** G-sec yields with official bulk — that's the pragmatic route for IN.
- **Recommendation**: **India: YES via DBIE registration** (cheap, official). **China: accept the gap for v1** — revisit with akshare or a licensed feed only if CN curve dynamics become analytically essential; IMF FSI + BIS DSR/credit already carry China's stress picture at quarterly cadence.

---

## Decision summary

| Source | Unique value | Keyless substitute | Effort | Verdict |
|---|---|---|---|---|
| NY Fed HHDC | US HH per-product stocks+delinquency (student/auto/card) | Partial (Z.1 stocks, FRED bank delinq) | Low (manual 5min/q) | **Acquire (manual now)** |
| India G-sec via RBI DBIE | IN daily sovereign curve | None | Low (registration) | **Acquire (register)** |
| EBA Risk Dashboard | EU stage-2/forbearance by country | ECB SUP NPE stocks | Low (manual 5min/q) | Optional, cheap |
| BoE IADB/MLAR | UK monthly credit + arrears | BIS quarterly + FSI | Medium | Defer |
| ChinaBond CGB curve | CN daily sovereign curve | None (quarterly stress only) | High (fragile scraping) | Defer / vendor later |

Net: two cheap acquisitions (NY Fed HHDC manual; DBIE registration) close most of the *high-value* gap; everything else is either already substituted or disproportionately expensive.
