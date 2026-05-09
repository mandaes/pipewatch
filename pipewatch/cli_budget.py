"""CLI for inspecting and managing alert budgets.

Usage examples::

    pipewatch-budget show --store budgets.json --job ingest_daily
    pipewatch-budget reset --store budgets.json --job ingest_daily
    pipewatch-budget show --store budgets.json --max-alerts 5 --window 600
"""
from __future__ import annotations

import argparse
import json
import sys

from pipewatch.budget import BudgetPolicy, BudgetStore


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-budget",
        description="Inspect and manage per-job alert budgets.",
    )
    parser.add_argument("command", choices=["show", "reset"], help="Sub-command")
    parser.add_argument("--store", default="budget_store.json", help="Path to budget store file")
    parser.add_argument("--job", required=True, help="Job name to inspect or reset")
    parser.add_argument("--max-alerts", type=int, default=10, help="Budget cap (default: 10)")
    parser.add_argument("--window", type=int, default=3600, help="Rolling window in seconds (default: 3600)")
    parser.add_argument("--format", choices=["text", "json"], default="text", dest="fmt")
    return parser.parse_args(argv)


def _render_text(job: str, policy: BudgetPolicy, store: BudgetStore) -> str:
    used = store.alert_count(job, policy.window_seconds)
    remaining = store.remaining(job, policy)
    exhausted = store.is_exhausted(job, policy)
    lines = [
        f"Job            : {job}",
        f"Window         : {policy.window_seconds}s",
        f"Budget         : {policy.max_alerts}",
        f"Used           : {used}",
        f"Remaining      : {remaining}",
        f"Exhausted      : {'yes' if exhausted else 'no'}",
    ]
    return "\n".join(lines)


def main(argv=None) -> None:
    args = parse_args(argv)
    policy = BudgetPolicy(max_alerts=args.max_alerts, window_seconds=args.window)
    store = BudgetStore(path=args.store)

    if args.command == "reset":
        store.reset(args.job)
        print(f"Budget reset for job '{args.job}'.")
        return

    # show
    if args.fmt == "json":
        used = store.alert_count(args.job, policy.window_seconds)
        payload = {
            "job": args.job,
            "window_seconds": policy.window_seconds,
            "max_alerts": policy.max_alerts,
            "used": used,
            "remaining": store.remaining(args.job, policy),
            "exhausted": store.is_exhausted(args.job, policy),
        }
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(args.job, policy, store))


if __name__ == "__main__":  # pragma: no cover
    main()
