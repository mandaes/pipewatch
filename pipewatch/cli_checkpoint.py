"""CLI entry-point for checkpoint inspection and management."""

from __future__ import annotations

import argparse
import sys

from pipewatch.checkpoint import CheckpointStore, Checkpoint, is_regressed

_DEFAULT_STORE = "checkpoints.json"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-checkpoint",
        description="Inspect and manage pipeline checkpoints.",
    )
    parser.add_argument(
        "--store",
        default=_DEFAULT_STORE,
        help="Path to checkpoint JSON store (default: %(default)s)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all stored checkpoints.")

    show = sub.add_parser("show", help="Show checkpoint for a specific job.")
    show.add_argument("job_name")

    record = sub.add_parser("record", help="Record a new checkpoint marker.")
    record.add_argument("job_name")
    record.add_argument("marker", help="Checkpoint marker value (e.g. ISO timestamp).")

    delete = sub.add_parser("delete", help="Delete checkpoint for a job.")
    delete.add_argument("job_name")

    check = sub.add_parser(
        "check-regression",
        help="Exit non-zero if new marker regresses vs stored checkpoint.",
    )
    check.add_argument("job_name")
    check.add_argument("marker")

    return parser.parse_args(argv)


def _render_checkpoint(cp: Checkpoint) -> str:
    return f"{cp.job_name}  marker={cp.marker}  recorded_at={cp.recorded_at.isoformat()}"


def main(argv=None) -> int:
    args = parse_args(argv)
    store = CheckpointStore(args.store)

    if args.command == "list":
        checkpoints = store.all()
        if not checkpoints:
            print("No checkpoints recorded.")
        for cp in checkpoints:
            print(_render_checkpoint(cp))

    elif args.command == "show":
        cp = store.get(args.job_name)
        if cp is None:
            print(f"No checkpoint found for job '{args.job_name}'.")
            return 1
        print(_render_checkpoint(cp))

    elif args.command == "record":
        cp = Checkpoint(job_name=args.job_name, marker=args.marker)
        store.save(cp)
        print(f"Checkpoint recorded: {_render_checkpoint(cp)}")

    elif args.command == "delete":
        removed = store.delete(args.job_name)
        if removed:
            print(f"Checkpoint for '{args.job_name}' deleted.")
        else:
            print(f"No checkpoint found for '{args.job_name}'.")
            return 1

    elif args.command == "check-regression":
        previous = store.get(args.job_name)
        if previous is None:
            print(f"No previous checkpoint for '{args.job_name}'; nothing to compare.")
            return 0
        current = Checkpoint(job_name=args.job_name, marker=args.marker)
        if is_regressed(previous, current):
            print(
                f"REGRESSION detected for '{args.job_name}': "
                f"new marker '{args.marker}' < stored marker '{previous.marker}'"
            )
            return 2
        print(f"OK: marker '{args.marker}' is not a regression.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
