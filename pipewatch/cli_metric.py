"""CLI entry point for pipewatch metric commands."""

from __future__ import annotations

import argparse
import json
import sys

from pipewatch.metric import MetricStore

_DEFAULT_STORE = "metric_store.json"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-metric",
        description="Record and inspect pipeline job metrics.",
    )
    parser.add_argument("--store", default=_DEFAULT_STORE, help="Path to metric store JSON file.")

    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="Record a metric value for a job.")
    rec.add_argument("job", help="Job name.")
    rec.add_argument("name", help="Metric name.")
    rec.add_argument("value", type=float, help="Numeric value to record.")

    show = sub.add_parser("show", help="Show metric history for a job.")
    show.add_argument("job", help="Job name.")
    show.add_argument("name", help="Metric name.")
    show.add_argument("--format", choices=["text", "json"], default="text", dest="fmt")

    summary = sub.add_parser("summary", help="Show summary statistics for a metric.")
    summary.add_argument("job", help="Job name.")
    summary.add_argument("name", help="Metric name.")

    sub.add_parser("jobs", help="List all jobs with recorded metrics.")

    return parser.parse_args(argv)


def _render_text(samples: list) -> str:
    if not samples:
        return "No samples found."
    lines = []
    for s in samples:
        lines.append(f"  [{s.recorded_at.isoformat()}]  {s.name} = {s.value}")
    return "\n".join(lines)


def main(argv=None) -> int:
    args = parse_args(argv)
    store = MetricStore(path=args.store)

    if args.command == "record":
        sample = store.record(args.job, args.name, args.value)
        print(f"Recorded: {sample.job}/{sample.name} = {sample.value} at {sample.recorded_at.isoformat()}")

    elif args.command == "show":
        samples = store.history(args.job, args.name)
        if args.fmt == "json":
            print(json.dumps([s.to_dict() for s in samples], indent=2))
        else:
            print(_render_text(samples))

    elif args.command == "summary":
        result = store.summary(args.job, args.name)
        print(f"Job:    {args.job}")
        print(f"Metric: {args.name}")
        for key, val in result.items():
            display = f"{val:.4f}" if isinstance(val, float) else str(val)
            print(f"  {key:<8}: {display}")

    elif args.command == "jobs":
        jobs = store.job_names()
        if jobs:
            for j in jobs:
                print(j)
        else:
            print("No jobs recorded yet.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
