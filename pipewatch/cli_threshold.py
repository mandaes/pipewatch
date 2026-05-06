"""CLI for evaluating threshold rules against the latest metric samples."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipewatch.metric import MetricStore
from pipewatch.threshold import ThresholdOp, ThresholdRule, evaluate_all


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="pipewatch-threshold",
        description="Evaluate threshold rules against stored metric samples.",
    )
    p.add_argument(
        "--rules", required=True, metavar="FILE",
        help="JSON file containing a list of threshold rule objects.",
    )
    p.add_argument(
        "--metrics", default="metrics.json", metavar="FILE",
        help="Path to the metrics store (default: metrics.json).",
    )
    p.add_argument(
        "--format", choices=["text", "json"], default="text",
        dest="fmt", help="Output format (default: text).",
    )
    p.add_argument(
        "--severity", default=None,
        help="Filter output to this severity level only.",
    )
    return p.parse_args(argv)


def _load_rules(path: str) -> list[ThresholdRule]:
    data = json.loads(Path(path).read_text())
    rules = []
    for item in data:
        rules.append(
            ThresholdRule(
                job=item["job"],
                metric=item["metric"],
                op=ThresholdOp(item["op"]),
                value=float(item["value"]),
                severity=item.get("severity", "warning"),
                description=item.get("description", ""),
            )
        )
    return rules


def _render_text(violations: list, severity: str | None) -> str:
    lines = []
    for v in violations:
        if severity and v.rule.severity != severity:
            continue
        lines.append(v.message)
    return "\n".join(lines) if lines else "No threshold violations."


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    rules = _load_rules(args.rules)

    store = MetricStore(args.metrics)
    # Build {job: {metric: latest_value}} from stored samples
    samples: dict[str, dict[str, float]] = {}
    for rule in rules:
        job_samples = store.latest(rule.job)
        if job_samples:
            samples.setdefault(rule.job, {})
            samples[rule.job][rule.metric] = job_samples.value

    violations = evaluate_all(rules, samples)

    if args.fmt == "json":
        filtered = [
            v.to_dict() for v in violations
            if args.severity is None or v.rule.severity == args.severity
        ]
        print(json.dumps(filtered, indent=2))
    else:
        print(_render_text(violations, args.severity))

    if violations:
        sys.exit(1)


if __name__ == "__main__":
    main()
