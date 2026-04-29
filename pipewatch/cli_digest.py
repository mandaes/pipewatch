"""CLI entry point for the pipewatch digest command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipewatch.digest import build_digest
from pipewatch.history import HistoryStore


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-digest",
        description="Print a health digest for all tracked pipeline jobs.",
    )
    parser.add_argument(
        "--history-file",
        default="pipewatch_history.jsonl",
        help="Path to the JSONL history file (default: pipewatch_history.jsonl)",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=20,
        help="Number of recent runs to include per job (default: 20)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format: text or json (default: text)",
    )
    return parser.parse_args(argv)


def _render_text(report) -> str:
    lines = [
        f"Digest generated at: {report.generated_at.isoformat()}",
        f"Jobs: {len(report.jobs)}  "
        f"Healthy: {report.healthy_count}  "
        f"Degraded: {report.degraded_count}  "
        f"Failing: {report.failing_count}",
        "-" * 60,
    ]
    for job in report.jobs:
        trend_dir = job.trend.direction.value if job.trend else "unknown"
        lines.append(
            f"  {job.job_name:<30}  "
            f"runs={job.total_runs:<4}  "
            f"fail_rate={job.failure_rate:.0%}  "
            f"last={job.last_state or 'n/a':<10}  "
            f"trend={trend_dir}"
        )
    return "\n".join(lines)


def main(argv=None) -> None:
    args = parse_args(argv)
    history_path = Path(args.history_file)
    if not history_path.exists():
        print(f"[pipewatch-digest] History file not found: {history_path}", file=sys.stderr)
        sys.exit(1)

    store = HistoryStore(str(history_path))
    report = build_digest(store, window=args.window)

    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(_render_text(report))


if __name__ == "__main__":  # pragma: no cover
    main()
