"""CLI tool for testing webhook delivery and managing webhook config."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from pipewatch.alert_rules import AlertEvent
from pipewatch.job_status import JobState
from pipewatch.webhook import build_webhook_notifier


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-webhook",
        description="Test or inspect webhook delivery for pipewatch alerts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ping = sub.add_parser("ping", help="Send a test alert event to a webhook URL.")
    ping.add_argument("url", help="Webhook URL to POST to.")
    ping.add_argument("--job", default="test_job", help="Job name for test event.")
    ping.add_argument(
        "--state",
        default="failed",
        choices=[s.value for s in JobState],
        help="State to simulate.",
    )
    ping.add_argument("--timeout", type=int, default=10, help="Request timeout seconds.")

    show = sub.add_parser("show-config", help="Pretty-print a webhook config dict.")
    show.add_argument("config_json", help="Inline JSON string of webhook config.")

    return parser.parse_args(argv)


def _cmd_ping(args: argparse.Namespace) -> int:
    notifier = build_webhook_notifier(
        {"url": args.url, "timeout_seconds": args.timeout}
    )
    event = AlertEvent(
        job_name=args.job,
        state=JobState(args.state),
        rule_name="ping",
        triggered_at=datetime.now(tz=timezone.utc),
    )
    try:
        notifier.send([event])
        print(f"[OK] Webhook delivered to {args.url}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Webhook delivery failed: {exc}", file=sys.stderr)
        return 1


def _cmd_show_config(args: argparse.Namespace) -> int:
    try:
        cfg = json.loads(args.config_json)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] Invalid JSON: {exc}", file=sys.stderr)
        return 1
    notifier = build_webhook_notifier(cfg)
    print(json.dumps(notifier.config.to_dict(), indent=2))
    return 0


def main(argv=None) -> None:
    args = parse_args(argv)
    if args.command == "ping":
        sys.exit(_cmd_ping(args))
    elif args.command == "show-config":
        sys.exit(_cmd_show_config(args))
