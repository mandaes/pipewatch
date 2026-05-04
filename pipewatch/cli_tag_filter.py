"""CLI sub-command: filter and display jobs by tag."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List

from pipewatch.cli import build_statuses, load_config
from pipewatch.tag_filter import parse_tag_filter


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-tag-filter",
        description="Filter pipeline jobs by tag and display their status.",
    )
    parser.add_argument(
        "--config",
        default="pipewatch.yaml",
        help="Path to pipewatch config file (default: pipewatch.yaml)",
    )
    parser.add_argument(
        "--require",
        metavar="TAG",
        nargs="*",
        default=[],
        dest="required",
        help="Tags that jobs must have",
    )
    parser.add_argument(
        "--exclude",
        metavar="TAG",
        nargs="*",
        default=[],
        dest="excluded",
        help="Tags that jobs must NOT have",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="fmt",
        help="Output format (default: text)",
    )
    return parser.parse_args(argv)


def _render_text(statuses) -> str:
    if not statuses:
        return "No matching jobs."
    lines = []
    for s in statuses:
        tags_str = ", ".join(s.tags) if s.tags else "(none)"
        lines.append(f"{s.job_name:30s}  state={s.state.value:10s}  tags=[{tags_str}]")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv)
    config = load_config(args.config)
    statuses = build_statuses(config)
    tag_filter = parse_tag_filter(
        required=args.required,
        excluded=args.excluded,
    )
    matched = tag_filter.filter_statuses(statuses)

    if args.fmt == "json":
        output = json.dumps([s.to_dict() for s in matched], indent=2, default=str)
        print(output)
    else:
        print(_render_text(matched))


if __name__ == "__main__":  # pragma: no cover
    main()
