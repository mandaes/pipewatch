"""CLI for inspecting and resetting circuit breaker state."""

from __future__ import annotations

import argparse
import json
import sys

from pipewatch.circuit_breaker import (
    BreakerState,
    CircuitBreakerPolicy,
    CircuitBreakerStore,
)

_DEFAULT_STORE = "circuit_breakers.json"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-circuit-breaker",
        description="Inspect and manage circuit breaker state for pipeline jobs.",
    )
    parser.add_argument("--store", default=_DEFAULT_STORE, help="Path to breaker store JSON file.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--failure-threshold", type=int, default=3, dest="failure_threshold"
    )
    parser.add_argument(
        "--recovery-window", type=int, default=300, dest="recovery_window_seconds"
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all breaker records.")

    reset_p = sub.add_parser("reset", help="Reset a breaker to CLOSED state.")
    reset_p.add_argument("job", help="Job name to reset.")

    trip_p = sub.add_parser("trip", help="Manually trip a breaker to OPEN state.")
    trip_p.add_argument("job", help="Job name to trip.")

    return parser.parse_args(argv)


def _render_text(records) -> str:
    if not records:
        return "No circuit breaker records found."
    lines = []
    for rec in records:
        symbol = {"closed": "✓", "open": "✗", "half_open": "~"}.get(rec.state.value, "?")
        tripped = rec.tripped_at.isoformat() if rec.tripped_at else "—"
        lines.append(
            f"[{symbol}] {rec.job:<30} state={rec.state.value:<10} "
            f"failures={rec.consecutive_failures}  tripped_at={tripped}"
        )
    return "\n".join(lines)


def main(argv=None) -> None:
    args = parse_args(argv)
    policy = CircuitBreakerPolicy(
        failure_threshold=args.failure_threshold,
        recovery_window_seconds=args.recovery_window_seconds,
    )
    store = CircuitBreakerStore(args.store)

    if args.command == "reset" or args.command is None and hasattr(args, "job"):
        if args.command == "reset":
            rec = store.get(args.job)
            from pipewatch.circuit_breaker import BreakerRecord
            reset_rec = BreakerRecord(job=args.job)
            store._records[args.job] = reset_rec
            store._save()
            print(f"Breaker for '{args.job}' reset to CLOSED.")
            return

    if args.command == "trip":
        from datetime import datetime, timezone
        from pipewatch.circuit_breaker import BreakerRecord
        rec = BreakerRecord(
            job=args.job,
            state=BreakerState.OPEN,
            consecutive_failures=policy.failure_threshold,
            tripped_at=datetime.now(timezone.utc),
        )
        store._records[args.job] = rec
        store._save()
        print(f"Breaker for '{args.job}' manually tripped to OPEN.")
        return

    # Default: list
    records = store.all_records()
    if args.format == "json":
        print(json.dumps([r.to_dict() for r in records], indent=2))
    else:
        print(_render_text(records))


if __name__ == "__main__":
    main()
