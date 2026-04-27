"""CLI sub-command: pipewatch export — dump status/history to stdout."""
from __future__ import annotations

import argparse
import sys

from pipewatch.cli import load_config, build_statuses
from pipewatch.export import (
    history_report_to_csv,
    history_report_to_json,
    statuses_to_csv,
    statuses_to_json,
)
from pipewatch.history import HistoryStore


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-export",
        description="Export pipeline status or history to JSON / CSV.",
    )
    parser.add_argument("--config", default="pipewatch.yml", help="Path to config file")
    parser.add_argument(
        "--format", choices=["json", "csv"], default="json", help="Output format"
    )
    parser.add_argument(
        "--source",
        choices=["status", "history"],
        default="status",
        help="What to export",
    )
    parser.add_argument("--history-db", default="pipewatch_history.db", help="History DB path")
    parser.add_argument("--limit", type=int, default=50, help="Max history entries per job")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    cfg = load_config(args.config)

    if args.source == "status":
        statuses = build_statuses(cfg)
        output = (
            statuses_to_json(statuses) if args.format == "json" else statuses_to_csv(statuses)
        )
    else:
        store = HistoryStore(args.history_db)
        output = (
            history_report_to_json(store, limit=args.limit)
            if args.format == "json"
            else history_report_to_csv(store, limit=args.limit)
        )

    sys.stdout.write(output)
    if output and not output.endswith("\n"):
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
