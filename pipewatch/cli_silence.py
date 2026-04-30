"""CLI for managing alert silence rules in pipewatch."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from pipewatch.silencer import SilenceRule, load_silence_rules, save_silence_rules

DEFAULT_SILENCE_FILE = "silences.json"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-silence",
        description="Manage alert silence rules.",
    )
    parser.add_argument(
        "--file", default=DEFAULT_SILENCE_FILE,
        help="Path to silence rules JSON file (default: silences.json)",
    )
    sub = parser.add_subparsers(dest="command")

    add_p = sub.add_parser("add", help="Add a new silence rule")
    add_p.add_argument("job", help="Job name to silence, or '*' for all jobs")
    add_p.add_argument("--reason", required=True, help="Reason for silencing")
    add_p.add_argument(
        "--hours", type=float, default=1.0,
        help="Duration in hours (default: 1.0)",
    )
    add_p.add_argument(
        "--states", nargs="*", default=[],
        help="Specific states to silence (default: all states)",
    )

    sub.add_parser("list", help="List active silence rules")
    sub.add_parser("prune", help="Remove expired silence rules")

    return parser.parse_args(argv)


def _render_rules(rules: list[SilenceRule]) -> str:
    if not rules:
        return "No silence rules found."
    lines = []
    now = datetime.now(timezone.utc)
    for i, r in enumerate(rules):
        active = "ACTIVE" if r.is_active(now) else "EXPIRED"
        states = ", ".join(r.states) if r.states else "all"
        lines.append(
            f"[{i}] {r.job_name} | {active} until {r.until.isoformat()} "
            f"| states: {states} | reason: {r.reason}"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.command == "add":
        rules = load_silence_rules(args.file)
        until = datetime.now(timezone.utc) + timedelta(hours=args.hours)
        rule = SilenceRule(
            job_name=args.job,
            reason=args.reason,
            until=until,
            states=args.states,
        )
        rules.append(rule)
        save_silence_rules(rules, args.file)
        print(f"Silence rule added for '{args.job}' until {until.isoformat()}.")
        return 0

    if args.command == "list":
        rules = load_silence_rules(args.file)
        print(_render_rules(rules))
        return 0

    if args.command == "prune":
        rules = load_silence_rules(args.file)
        now = datetime.now(timezone.utc)
        active = [r for r in rules if r.is_active(now)]
        removed = len(rules) - len(active)
        save_silence_rules(active, args.file)
        print(f"Pruned {removed} expired rule(s). {len(active)} rule(s) remaining.")
        return 0

    print("No command specified. Use --help for usage.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
