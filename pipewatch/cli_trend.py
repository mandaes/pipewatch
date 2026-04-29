"""CLI for inspecting job trend analysis from history."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List

from pipewatch.history import HistoryStore
from pipewatch.trend import TrendDirection, TrendResult, analyze_trend


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-trend",
        description="Analyze failure-rate trends for ETL jobs.",
    )
    parser.add_argument(
        "--history",
        default="pipewatch_history.json",
        metavar="FILE",
        help="Path to history JSON file (default: pipewatch_history.json)",
    )
    parser.add_argument(
        "--job",
        metavar="JOB_NAME",
        default=None,
        help="Filter to a single job name",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=10,
        metavar="N",
        help="Number of recent entries to analyse per job (default: 10)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="fmt",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--only-degrading",
        action="store_true",
        help="Only show jobs whose trend is DEGRADING",
    )
    return parser.parse_args(argv)


def _render_text(results: List[TrendResult]) -> str:
    if not results:
        return "No trend data available."
    lines = []
    for r in results:
        arrow = {"DEGRADING": "↑", "IMPROVING": "↓", "STABLE": "→"}.get(
            r.direction.value, "?"
        )
        lines.append(
            f"{r.job_name:30s}  {arrow} {r.direction.value:10s}  "
            f"rate={r.failure_rate:.2f}  delta={r.delta:+.2f}  "
            f"samples={r.sample_count}"
        )
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv)
    store = HistoryStore(args.history)
    all_entries = store.load()

    job_names = (
        [args.job] if args.job else sorted({e.job_name for e in all_entries})
    )

    results = []
    for name in job_names:
        entries = [e for e in all_entries if e.job_name == name]
        result = analyze_trend(name, entries, window=args.window)
        if args.only_degrading and result.direction != TrendDirection.DEGRADING:
            continue
        results.append(result)

    if args.fmt == "json":
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        print(_render_text(results))


if __name__ == "__main__":  # pragma: no cover
    main()
