"""Summarise history store data for CLI reporting."""

from __future__ import annotations

from collections import Counter
from typing import Dict, List

from pipewatch.history import HistoryEntry, HistoryStore


def state_summary(entries: List[HistoryEntry]) -> Dict[str, int]:
    """Return a count of each state across the provided entries."""
    counter: Counter = Counter(e.state for e in entries)
    return dict(counter)


def failure_rate(entries: List[HistoryEntry]) -> float:
    """Return the fraction of entries that are in a failed state (0.0 – 1.0)."""
    if not entries:
        return 0.0
    failed = sum(1 for e in entries if e.state == "failed")
    return failed / len(entries)


def last_state(entries: List[HistoryEntry]) -> str | None:
    """Return the state of the most recent entry, or None if empty."""
    if not entries:
        return None
    return entries[-1].state


def job_report(store: HistoryStore, job_name: str, limit: int = 50) -> dict:
    """Build a summary report dict for a single job."""
    entries = store.recent_for_job(job_name, limit=limit)
    return {
        "job_name": job_name,
        "total_entries": len(entries),
        "last_state": last_state(entries),
        "failure_rate": round(failure_rate(entries), 4),
        "state_summary": state_summary(entries),
    }


def all_jobs_report(store: HistoryStore, limit: int = 50) -> List[dict]:
    """Build summary reports for every distinct job found in the store."""
    all_entries = store.read_all()
    job_names = list(dict.fromkeys(e.job_name for e in all_entries))  # preserve order, dedupe
    return [job_report(store, name, limit=limit) for name in job_names]


def print_report(store: HistoryStore, job_name: str | None = None) -> None:
    """Print a human-readable report to stdout."""
    reports = [job_report(store, job_name)] if job_name else all_jobs_report(store)
    if not reports:
        print("No history found.")
        return
    for r in reports:
        print(f"Job: {r['job_name']}")
        print(f"  Last state   : {r['last_state'] or 'n/a'}")
        print(f"  Total polls  : {r['total_entries']}")
        print(f"  Failure rate : {r['failure_rate'] * 100:.1f}%")
        summary = ", ".join(f"{s}={c}" for s, c in sorted(r["state_summary"].items()))
        print(f"  State counts : {summary or 'n/a'}")
        print()
