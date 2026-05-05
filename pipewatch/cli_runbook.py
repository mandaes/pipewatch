"""CLI for managing and querying pipewatch runbook entries."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipewatch.runbook import RunbookEntry, RunbookStore

DEFAULT_RUNBOOK_FILE = "runbook.json"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipewatch-runbook",
        description="Manage runbook links for pipeline jobs.",
    )
    parser.add_argument(
        "--runbook-file",
        default=DEFAULT_RUNBOOK_FILE,
        help="Path to runbook JSON file (default: %(default)s)",
    )
    sub = parser.add_subparsers(dest="command")

    # list
    sub.add_parser("list", help="List all runbook entries.")

    # lookup
    lk = sub.add_parser("lookup", help="Look up runbook entry for a job.")
    lk.add_argument("job_name", help="Job name to look up.")

    # add
    add = sub.add_parser("add", help="Add a new runbook entry.")
    add.add_argument("job_name", help="Job name or '*' for wildcard.")
    add.add_argument("url", help="Runbook URL.")
    add.add_argument("--notes", default="", help="Optional notes.")

    return parser.parse_args(argv)


def _load_store(path: str) -> RunbookStore:
    p = Path(path)
    if p.exists():
        with p.open() as fh:
            return RunbookStore.from_list(json.load(fh))
    return RunbookStore()


def _save_store(store: RunbookStore, path: str) -> None:
    with open(path, "w") as fh:
        json.dump(store.all_entries(), fh, indent=2)


def main(argv=None) -> None:
    args = parse_args(argv)
    store = _load_store(args.runbook_file)

    if args.command == "list":
        entries = store.all_entries()
        if not entries:
            print("No runbook entries found.")
        for e in entries:
            notes_part = f"  # {e['notes']}" if e["notes"] else ""
            print(f"{e['job_name']:30s}  {e['url']}{notes_part}")

    elif args.command == "lookup":
        entry = store.lookup(args.job_name)
        if entry is None:
            print(f"No runbook entry found for '{args.job_name}'.")
            sys.exit(1)
        print(f"Job   : {entry.job_name}")
        print(f"URL   : {entry.url}")
        if entry.notes:
            print(f"Notes : {entry.notes}")

    elif args.command == "add":
        store.add(RunbookEntry(job_name=args.job_name, url=args.url, notes=args.notes))
        _save_store(store, args.runbook_file)
        print(f"Added runbook entry for '{args.job_name}'.")

    else:
        parse_args(["--help"])


if __name__ == "__main__":  # pragma: no cover
    main()
