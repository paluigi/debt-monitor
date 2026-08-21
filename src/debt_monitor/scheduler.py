"""Orchestrator (run collectors concurrently, record run log) + APScheduler
daily wiring."""

import asyncio
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential_jitter

from debt_monitor.collectors.base import BaseCollector, registered_collectors
from debt_monitor.config import Settings, get_settings
from debt_monitor.db import MongoRepository
from debt_monitor.http import AsyncHttpClient
from debt_monitor.models import CollectResult

logger = logging.getLogger(__name__)
CONCURRENCY = 4


class Orchestrator:
    """Owns the HTTP client and Mongo repository; runs collectors in parallel."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.http = AsyncHttpClient(proxy=self.settings.webshare_proxy)
        self.repo = MongoRepository(self.settings)

    async def run(self, names: list[str] | None = None) -> list[CollectResult]:
        registry = registered_collectors()
        if names:
            unknown = [n for n in names if n not in registry]
            if unknown:
                raise KeyError(f"unknown collector(s): {unknown}; known: {sorted(registry)}")
            classes = [registry[n] for n in names]
        else:
            classes = list(registry.values())

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def run_one(cls: type[BaseCollector]) -> CollectResult:
            async with semaphore:
                collector = cls(self.http, self.repo, self.settings)
                started = datetime.now(UTC)
                try:
                    async for attempt in AsyncRetrying(
                        stop=stop_after_attempt(2),
                        wait=wait_exponential_jitter(initial=1, max=30),
                        reraise=True,
                    ):
                        with attempt:
                            result = await collector.collect()
                    result.started_at = started
                except Exception as exc:
                    logger.exception("collector %s failed", cls.name)
                    result = CollectResult(
                        source=cls.name,
                        status="failed",
                        detail=f"{type(exc).__name__}: {exc}",
                        started_at=started,
                    )
                try:
                    await self.repo.record_run(result)
                except Exception:
                    logger.exception("could not record run for %s", cls.name)
                logger.info(
                    "%s -> %s (%d docs) %s",
                    result.source,
                    result.status,
                    result.n_docs,
                    result.detail,
                )
                return result

        return list(await asyncio.gather(*(run_one(cls) for cls in classes)))

    async def close(self) -> None:
        await self.http.aclose()
        self.repo.close()


def build_scheduler(orchestrator: Orchestrator) -> AsyncIOScheduler:
    """Daily cron trigger in the configured local timezone, with jitter."""
    settings = orchestrator.settings
    scheduler = AsyncIOScheduler(timezone=settings.schedule_tz)
    scheduler.add_job(
        orchestrator.run,
        CronTrigger(hour=settings.schedule_hour, minute=settings.schedule_minute),
        id="daily_collect",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3_600,
        jitter=900,
        replace_existing=True,
    )
    return scheduler
