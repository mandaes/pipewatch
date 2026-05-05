"""CLI entry-point for pruning stale history entries from a JSON history file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

from pipewatch.history import HistoryEntry
from pipewatch.retention import RetentionPolicy, prune_store


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-retention",
        description="Prune old history entries from a pipewatch history file.",
    )
    parser.add_argument(
        "--history",
        default="history.json",
        help="Path to the history JSON file (default: history.json).",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=None,
        metavar="DAYS",
        help="Remove entries older than DAYS days.",
    )
    parser.add_argument(
        "--max-entries",
        type=int,
        default=None,
        metavar="N",
        help="Keep at most N most-recent entries per job.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be removed without modifying the file.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)

    if args.max_age_days is None and args.max_entries is None:
        print("Error: at least one of --max-age-days or --max-entries is required.", file=sys.stderr)
        sys.exit(1)

    history_path = Path(args.history)
    if not history_path.exists():
        print(f"Error: history file not found: {history_path}", file=sys.stderr)
        sys.exit(1)

    raw: Dict[str, List[dict]] = json.loads(history_path.read_text())
    store: Dict[str, List[HistoryEntry]] = {
        job: [HistoryEntry.from_dict(e) for e in entries]
        for job, entries in raw.items()
    }

    policy = RetentionPolicy(
        max_age_days=args.max_age_days,
        max_entries=args.max_entries,
    )
    pruned = prune_store(store, policy)

    before_total = sum(len(v) for v in store.values())
    after_total = sum(len(v) for v in pruned.values())
    removed = before_total - after_total

    if args.dry_run:
        print(f"Dry run: would remove {removed} entr{'y' if removed == 1 else 'ies'} "
              f"({before_total} -> {after_total}).")
        return

    serialised = {
        job: [e.to_dict() for e in entries]
        for job, entries in pruned.items()
    }
    history_path.write_text(json.dumps(serialised, indent=2))
    print(f"Pruned {removed} entr{'y' if removed == 1 else 'ies'} "
          f"({before_total} -> {after_total}). File updated: {history_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
