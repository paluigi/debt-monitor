"""CLI entry point: `collect`, `schedule`, `list`."""

import argparse
import asyncio
import logging
import signal
import sys

from dotenv import load_dotenv

from debt_monitor.collectors.base import registered_collectors
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


if __name__ == "__main__":
    main()
