"""CLI entry-point: pipewatch-anomaly — report anomalies from job history."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List

from pipewatch.anomaly import AnomalyResult, analyze_anomalies
from pipewatch.history import HistoryStore


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-anomaly",
        description="Detect anomalies in pipeline job history.",
    )
    parser.add_argument(
        "--store",
        default="history.json",
        metavar="PATH",
        help="Path to the history JSON store (default: history.json)",
    )
    parser.add_argument(
        "--job",
        metavar="NAME",
        help="Analyse a single job; omit to analyse all jobs",
    )
    parser.add_argument(
        "--z-threshold",
        type=float,
        default=2.5,
        dest="z_threshold",
        help="Z-score threshold for duration spike detection (default: 2.5)",
    )
    parser.add_argument(
        "--failure-window",
        type=int,
        default=5,
        dest="failure_window",
        help="Number of recent runs to check for failure spikes (default: 5)",
    )
    parser.add_argument(
        "--failure-threshold",
        type=float,
        default=0.6,
        dest="failure_threshold",
        help="Failure rate threshold to trigger spike alert (default: 0.6)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="fmt",
        help="Output format: text or json (default: text)",
    )
    return parser.parse_args(argv)


def _render_text(results: List[AnomalyResult]) -> str:
    if not results:
        return "No anomalies detected."
    lines = []
    for r in results:
        lines.append(f"[{r.kind.value}] {r.job_name} (score={r.score:.2f}): {r.detail}")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)

    store = HistoryStore(args.store)
    all_entries = store.load()

    if args.job:
        job_names = [args.job]
    else:
        job_names = sorted({e.job_name for e in all_entries})

    all_anomalies: List[AnomalyResult] = []
    for name in job_names:
        entries = [e for e in all_entries if e.job_name == name]
        anomalies = analyze_anomalies(
            name,
            entries,
            z_threshold=args.z_threshold,
            failure_window=args.failure_window,
            failure_threshold=args.failure_threshold,
        )
        all_anomalies.extend(anomalies)

    if args.fmt == "json":
        print(json.dumps([a.to_dict() for a in all_anomalies], indent=2))
    else:
        print(_render_text(all_anomalies))

    return 1 if all_anomalies else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
