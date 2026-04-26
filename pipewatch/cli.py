"""CLI entry point for pipewatch — starts the scheduler from a config file."""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from typing import List

from pipewatch.alert_rules import AlertRule
from pipewatch.job_status import JobState, JobStatus
from pipewatch.notifier import StdoutNotifier
from pipewatch.scheduler import Scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_config(path: str) -> dict:
    """Load a JSON config file."""
    with open(path) as f:
        return json.load(f)


def build_rules(config: dict) -> List[AlertRule]:
    """Build AlertRule objects from config dicts."""
    rules = []
    for r in config.get("rules", []):
        rules.append(
            AlertRule(
                job_id=r.get("job_id"),
                match_states=[JobState(s) for s in r.get("match_states", [])],
                reason=r["reason"],
            )
        )
    return rules


def build_statuses(config: dict) -> List[JobStatus]:
    """Build static JobStatus list from config (used for demo/testing)."""
    statuses = []
    for s in config.get("jobs", []):
        last_success = (
            datetime.fromisoformat(s["last_success"]) if s.get("last_success") else None
        )
        last_run = (
            datetime.fromisoformat(s["last_run"]) if s.get("last_run") else None
        )
        statuses.append(
            JobStatus(
                job_id=s["job_id"],
                state=JobState(s["state"]),
                last_success=last_success,
                last_run=last_run,
                stale_threshold_minutes=s.get("stale_threshold_minutes", 60),
            )
        )
    return statuses


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="pipewatch",
        description="Monitor ETL pipeline health and alert on stale or failed jobs.",
    )
    parser.add_argument("config", help="Path to JSON config file")
    parser.add_argument(
        "--interval", type=int, default=60, help="Poll interval in seconds (default: 60)"
    )
    parser.add_argument(
        "--cycles", type=int, default=None, help="Number of cycles to run (default: infinite)"
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.error("Failed to load config: %s", exc)
        return 1

    rules = build_rules(config)
    statuses = build_statuses(config)
    notifiers = [StdoutNotifier(prefix="[ALERT]")]

    scheduler = Scheduler(
        fetch_statuses=lambda: statuses,
        rules=rules,
        notifiers=notifiers,
        interval_seconds=args.interval,
    )

    logger.info("Starting pipewatch with %d rule(s) and %d job(s).", len(rules), len(statuses))
    scheduler.run(max_cycles=args.cycles)
    return 0


if __name__ == "__main__":
    sys.exit(main())
