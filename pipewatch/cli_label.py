"""CLI entry-point for label-based job filtering.

Usage examples::

    pipewatch-label --require env=prod
    pipewatch-label --require env=prod --exclude debug --statuses statuses.json
    pipewatch-label --selector 'env=prod,!debug'
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from pipewatch.job_status import JobStatus, JobState
from pipewatch.label import LabelSelector, filter_by_labels, parse_label_selector


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-label",
        description="Filter pipeline jobs by label selectors.",
    )
    parser.add_argument(
        "--statuses",
        default="statuses.json",
        metavar="FILE",
        help="JSON file produced by pipewatch-export (default: statuses.json).",
    )
    parser.add_argument(
        "--require",
        nargs="+",
        default=[],
        metavar="KEY=VALUE",
        help="Required label key=value pairs.",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=[],
        metavar="KEY",
        help="Label keys that must be absent.",
    )
    parser.add_argument(
        "--selector",
        default="",
        metavar="EXPR",
        help="Compact selector string, e.g. 'env=prod,!debug'. "
             "Merged with --require / --exclude.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    return parser.parse_args(argv)


def _build_selector(args: argparse.Namespace) -> LabelSelector:
    base = parse_label_selector(args.selector)
    for token in args.require:
        key, _, value = token.partition("=")
        base.required[key.strip()] = value.strip()
    for key in args.exclude:
        if key not in base.excluded_keys:
            base.excluded_keys.append(key)
    return base


def _render_text(statuses: List[JobStatus]) -> str:
    if not statuses:
        return "No jobs matched the label selector."
    lines = []
    for s in statuses:
        labels_str = ", ".join(f"{k}={v}" for k, v in (s.labels or {}).items())
        state = s.state.value if isinstance(s.state, JobState) else str(s.state)
        lines.append(f"{s.job_id}  [{state}]  labels: {labels_str or '(none)'}")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> None:  # pragma: no cover
    args = parse_args(argv)
    path = Path(args.statuses)
    if not path.exists():
        print(f"[pipewatch-label] statuses file not found: {path}", file=sys.stderr)
        sys.exit(1)

    raw: list = json.loads(path.read_text())
    statuses = [JobStatus(**entry) for entry in raw]

    selector = _build_selector(args)
    matched = filter_by_labels(statuses, selector)

    if args.format == "json":
        print(json.dumps([s.to_dict() for s in matched], indent=2))
    else:
        print(_render_text(matched))
