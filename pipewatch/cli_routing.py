"""CLI for inspecting and testing the alert routing configuration."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List

from pipewatch.alert_rules import AlertEvent
from pipewatch.routing import Router, RoutingRule


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-routing",
        description="Inspect or test alert routing rules.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- show-rules ---
    sub.add_parser("show-rules", help="Print all configured routing rules as JSON.")

    # --- test-event ---
    te = sub.add_parser("test-event", help="Simulate an event and show which notifiers would fire.")
    te.add_argument("--job", default="example_job", help="Job name to simulate.")
    te.add_argument("--state", default="failed", help="State to simulate (default: failed).")
    te.add_argument(
        "--config",
        default="routing.json",
        help="Path to routing config JSON (default: routing.json).",
    )

    return parser.parse_args(argv)


def _load_router(config_path: str) -> Router:
    """Load a Router from a JSON config file."""
    try:
        with open(config_path) as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        print(f"[pipewatch-routing] Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    rules = [
        RoutingRule(
            notifiers=item.get("notifiers", []),
            job_pattern=item.get("job_pattern"),
            min_severity=item.get("min_severity"),
            states=item.get("states"),
        )
        for item in raw.get("rules", [])
    ]
    fallback = raw.get("fallback_notifier")
    return Router(rules=rules, fallback_notifier=fallback)


def main(argv: List[str] | None = None) -> None:  # pragma: no cover
    args = parse_args(argv)

    if args.command == "show-rules":
        router = _load_router(getattr(args, "config", "routing.json"))
        output = [r.to_dict() for r in router.rules]
        print(json.dumps(output, indent=2))
        return

    if args.command == "test-event":
        from datetime import datetime, timezone

        router = _load_router(args.config)
        event = AlertEvent(
            job_name=args.job,
            state=args.state,
            triggered_at=datetime.now(timezone.utc),
            rule_name="<cli-test>",
        )
        targets = router._resolve_targets(event)  # noqa: SLF001
        if targets:
            print(f"Event ({args.job!r}, state={args.state!r}) would route to: {targets}")
        else:
            print(f"Event ({args.job!r}, state={args.state!r}) matched no notifiers.")
        return


if __name__ == "__main__":  # pragma: no cover
    main()
