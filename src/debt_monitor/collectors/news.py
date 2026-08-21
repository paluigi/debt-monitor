"""Economic news layer: official RSS feeds + Google News queries + GDELT +
Finnhub economy news (dossier 09). Articles are deduped by URL hash.

GDELT is rate-limited to 1 request / 5 s (HTTP 429) — a single artlist call per
run stays well inside that. Dead official feeds (Reuters, IMF, WB, BIS, US
Treasury, NY Fed, ESRB) are replaced by Google News query feeds.
"""

import asyncio
import hashlib
from datetime import UTC, datetime

import feedparser

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
FINNHUB_URL = "https://finnhub.io/api/v1/news"

FEEDS: tuple[tuple[str, str], ...] = (
    ("ecb", "https://www.ecb.europa.eu/rss/press.html"),
    ("fed", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("boe", "https://www.bankofengland.co.uk/rss/news"),
    ("fsb", "https://www.fsb.org/feed/"),
    ("fdic", "https://www.fdic.gov/rss.xml"),
    (
        "cnbc_economy",
        ("https://search.cnbc.com/rs/search/combinedcms/view.xml" "?partnerId=wrss01&id=100003114"),
    ),
    ("marketwatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    (
        "gnews_debt_crisis",
        ("https://news.google.com/rss/search?q=debt+crisis+bank&hl=en-US&gl=US&ceid=US:en"),
    ),
    (
        "gnews_household_debt",
        (
            "https://news.google.com/rss/search?q=household+debt+delinquency"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    ),
    (
        "gnews_npl",
        (
            "https://news.google.com/rss/search?q=non-performing+loans+bank"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    ),
)

GDELT_QUERY = "(sovereign debt OR bank failure OR nonperforming loans)"


def _article_id(link: str, fallback: str) -> str:
    return hashlib.sha256((link or fallback).encode()).hexdigest()


def _published(entry) -> str:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed:
        return datetime(*parsed[:6], tzinfo=UTC).isoformat()
    return getattr(entry, "published", "")


def parse_feed(data: bytes, feed: str, fetched_at: datetime) -> list[dict]:
    parsed = feedparser.parse(data)
    docs = []
    for entry in parsed.entries:
        link = getattr(entry, "link", "")
        title = getattr(entry, "title", "")
        if not link and not title:
            continue
        docs.append(
            {
                "_id": _article_id(link, f"{feed}|{title}|{_published(entry)}"),
                "source": "news",
                "dataset": "rss",
                "feed": feed,
                "title": title,
                "link": link,
                "published": _published(entry),
                "summary": (getattr(entry, "summary", "") or "")[:1_000],
                "fetched_at": fetched_at,
            }
        )
    return docs


def parse_gdelt(js: dict, fetched_at: datetime) -> list[dict]:
    docs = []
    for article in js.get("articles", []):
        link = article.get("url", "")
        docs.append(
            {
                "_id": _article_id(link, article.get("title", "")),
                "source": "news",
                "dataset": "gdelt",
                "feed": article.get("domain", ""),
                "title": article.get("title", ""),
                "link": link,
                "published": article.get("seendate", ""),
                "summary": "",
                "fetched_at": fetched_at,
            }
        )
    return docs


def parse_finnhub(items: list[dict], fetched_at: datetime) -> list[dict]:
    docs = []
    for item in items:
        link = item.get("url", "")
        published = ""
        if item.get("datetime"):
            published = datetime.fromtimestamp(item["datetime"], tz=UTC).isoformat()
        docs.append(
            {
                "_id": _article_id(link, str(item.get("id", ""))),
                "source": "news",
                "dataset": "finnhub",
                "feed": item.get("source", ""),
                "title": item.get("headline", ""),
                "link": link,
                "published": published,
                "summary": (item.get("summary", "") or "")[:1_000],
                "fetched_at": fetched_at,
            }
        )
    return docs


@register
class NewsCollector(BaseCollector):
    name = "news"
    collection = "news"
    description = "RSS feeds + Google News + GDELT + Finnhub economy news, daily"

    async def collect(self) -> CollectResult:
        fetched_at = datetime.now(UTC)
        parts: list[str] = []
        failures: list[str] = []
        total = 0

        async def fetch_feed(feed: str, url: str) -> None:
            try:
                data = await self.http.get_bytes(url, timeout=45.0)
                docs = await asyncio.to_thread(parse_feed, data, feed, fetched_at)
            except Exception as exc:
                failures.append(f"{feed}: {type(exc).__name__}")
                return
            nonlocal total
            total += await self.repo.upsert_docs(self.collection, docs)
            parts.append(f"{feed}: {len(docs)}")

        await asyncio.gather(*(fetch_feed(feed, url) for feed, url in FEEDS))

        try:
            js = await self.http.get_json(
                GDELT_URL,
                params={
                    "query": GDELT_QUERY,
                    "mode": "artlist",
                    "maxrecords": 75,
                    "format": "json",
                    "timespan": "3d",
                },
                timeout=60.0,
            )
            docs = parse_gdelt(js, fetched_at)
            total += await self.repo.upsert_docs(self.collection, docs)
            parts.append(f"gdelt: {len(docs)}")
        except Exception as exc:
            failures.append(f"gdelt: {type(exc).__name__}")

        if self.settings.finnhub_api_key:
            try:
                items = await self.http.get_json(
                    FINNHUB_URL,
                    params={"category": "economy", "token": self.settings.finnhub_api_key},
                )
                docs = parse_finnhub(items or [], fetched_at)
                total += await self.repo.upsert_docs(self.collection, docs)
                parts.append(f"finnhub: {len(docs)}")
            except Exception as exc:
                failures.append(f"finnhub: {type(exc).__name__}")
        else:
            parts.append("finnhub: skipped (no key)")

        status = "failed" if not parts else "ok"
        return CollectResult(
            source=self.name,
            status=status,
            n_docs=total,
            detail="; ".join(parts + [f"FAILED {x}" for x in failures]),
        )
