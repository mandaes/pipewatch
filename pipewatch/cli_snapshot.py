"""CLI for managing and diffing job status snapshots."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipewatch.snapshot import SnapshotStore
from pipewatch.snapshot_diff import diff_snapshots


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage pipewatch snapshots")
    parser.add_argument("--store", default="snapshots.json", help="Path to snapshot store file")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all saved snapshots")

    show_p = sub.add_parser("show", help="Show a snapshot by ID")
    show_p.add_argument("snapshot_id")

    diff_p = sub.add_parser("diff", help="Diff two snapshots")
    diff_p.add_argument("before_id")
    diff_p.add_argument("after_id")
    diff_p.add_argument("--format", choices=["text", "json"], default="text")

    del_p = sub.add_parser("delete", help="Delete a snapshot by ID")
    del_p.add_argument("snapshot_id")

    return parser.parse_args(argv)


def _render_diff_text(diff) -> str:
    lines = [f"Diff: {diff.before_id[:8]} → {diff.after_id[:8]}"]
    lines.append(f"Changed: {len(diff.changed_jobs)} / {len(diff.diffs)} jobs")
    for d in diff.diffs:
        if d.appeared:
            lines.append(f"  + {d.job_name}  (new: {d.after_state})")
        elif d.disappeared:
            lines.append(f"  - {d.job_name}  (was: {d.before_state})")
        elif d.changed:
            lines.append(f"  ~ {d.job_name}  {d.before_state} → {d.after_state}")
    return "\n".join(lines)


def main(argv=None) -> None:
    args = parse_args(argv)
    store = SnapshotStore(Path(args.store))

    if args.command == "list":
        snaps = store.list_snapshots()
        if not snaps:
            print("No snapshots found.")
            return
        for s in snaps:
            label = f"  [{s.label}]" if s.label else ""
            print(f"{s.snapshot_id}  {s.taken_at.isoformat()}{label}  ({len(s.statuses)} jobs)")

    elif args.command == "show":
        snap = store.get_snapshot(args.snapshot_id)
        if snap is None:
            print(f"Snapshot {args.snapshot_id!r} not found.", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(snap.to_dict(), indent=2))

    elif args.command == "diff":
        before = store.get_snapshot(args.before_id)
        after = store.get_snapshot(args.after_id)
        if before is None or after is None:
            missing = args.before_id if before is None else args.after_id
            print(f"Snapshot {missing!r} not found.", file=sys.stderr)
            sys.exit(1)
        result = diff_snapshots(before, after)
        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(_render_diff_text(result))

    elif args.command == "delete":
        removed = store.delete_snapshot(args.snapshot_id)
        if removed:
            print(f"Deleted snapshot {args.snapshot_id}.")
        else:
            print(f"Snapshot {args.snapshot_id!r} not found.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
