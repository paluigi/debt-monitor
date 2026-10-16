"""CLI entry point: `collect`, `schedule`, `list`, `metrics`, `coverage`."""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv

from debt_monitor.collectors.base import registered_collectors
from debt_monitor.config import get_settings
from debt_monitor.db import MongoRepository
from debt_monitor.metrics import compute_and_store, coverage_rows, to_tidy_csv
from debt_monitor.scheduler import Orchestrator, build_scheduler

logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def _collect(sources: list[str]) -> int:
    orchestrator = Orchestrator()
    try:
        results = await orchestrator.run(sources)
    finally:
        await orchestrator.close()
    print("\n{:14} {:8} {:>7}  {}".format("SOURCE", "STATUS", "DOCS", "DETAIL"))
    for result in sorted(results, key=lambda r: r.source):
        print(f"{result.source:14} {result.status:8} {result.n_docs:7d}  {result.detail}")
    failed = [r for r in results if r.status == "failed"]
    return 1 if failed else 0


async def _schedule() -> None:
    orchestrator = Orchestrator()
    scheduler = build_scheduler(orchestrator)
    scheduler.start()
    job = scheduler.get_job("daily_collect")
    logger.info("scheduler started; next run: %s", job.next_run_time)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()
    logger.info("shutting down")
    scheduler.shutdown(wait=False)
    await orchestrator.close()


async def _metrics(actor: str, country: str, metric: str, export: bool) -> int:
    repo = MongoRepository(get_settings())
    try:
        counts = await compute_and_store(repo)
        print(f"computed: {counts['computed']} metrics stored: {counts['stored']}")
        query: dict = {}
        if actor:
            query["actor"] = actor
        if country:
            query["country"] = country
        if metric:
            query["metric"] = metric
        rows = await repo.find_many("metrics", query)
        for info in coverage_rows(rows):
            print(f"  {info['actor']:28} {info['metric']:24} {info['denominator']:22} {info['countries']:3d} countries  latest {info['latest']}")
        if export:
            out = Path("data/metrics/metrics.csv")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(to_tidy_csv(rows))
            print(f"exported {len(rows)} rows -> {out}")
        return 0
    finally:
        repo.close()


async def _coverage() -> int:
    repo = MongoRepository(get_settings())
    try:
        rows = await repo.find_many("metrics", {})
        if not rows:
            print("no metrics stored yet — run `debt-monitor metrics` first")
            return 1
        for info in coverage_rows(rows):
            print(f"  {info['actor']:28} {info['metric']:24} {info['denominator']:22} {info['countries']:3d} countries  latest {info['latest']}")
        return 0
    finally:
        repo.close()


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="debt-monitor",
        description="Collect debt-market data into MongoDB (see sources/ dossiers).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    collect_parser = sub.add_parser("collect", help="run collectors once")
    collect_parser.add_argument(
        "sources",
        nargs="*",
        help="collector names (default: all; see `list`)",
    )

    sub.add_parser("schedule", help="run the daily scheduler forever")
    sub.add_parser("list", help="list registered collectors")

    metrics_parser = sub.add_parser("metrics", help="compute derived metrics from stored observations")
    metrics_parser.add_argument("--actor", choices=["households", "non_financial_corporations", "financial_corporations", "government"])
    metrics_parser.add_argument("--country", help="ISO2 country code filter")
    metrics_parser.add_argument("--metric", choices=["interest_to_income", "debt_service_to_income", "debt_to_income"])
    metrics_parser.add_argument("--export", action="store_true", help="also write data/metrics/metrics.csv")

    sub.add_parser("coverage", help="show metrics coverage summary")

    args = parser.parse_args()
    _configure_logging(args.verbose)

    if args.command == "list":
        registry = registered_collectors()
        print(f"{len(registry)} collectors (one MongoDB collection each):")
        for name in sorted(registry):
            cls = registry[name]
            print(f"  {name:14} -> {cls.collection:14} {cls.description}")
        sys.exit(0)

    if args.command == "collect":
        sys.exit(asyncio.run(_collect(args.sources)))

    if args.command == "schedule":
        asyncio.run(_schedule())

    if args.command == "metrics":
        sys.exit(asyncio.run(_metrics(args.actor, args.country, args.metric, args.export)))

    if args.command == "coverage":
        sys.exit(asyncio.run(_coverage()))


if __name__ == "__main__":
    main()
