"""Reporting utilities for job history stored via HistoryStore."""
from __future__ import annotations

from collections import Counter
from typing import List, Optional

from pipewatch.history import HistoryEntry, HistoryStore
from pipewatch.job_status import JobState


def state_summary(entries: List[HistoryEntry]) -> Counter:
    """Return a Counter of JobState values across *entries*."""
    return Counter(e.state for e in entries)


def failure_rate(entries: List[HistoryEntry]) -> float:
    """Return fraction of entries whose state is FAILED (0.0 – 1.0)."""
    if not entries:
        return 0.0
    failed = sum(1 for e in entries if e.state == JobState.FAILED)
    return failed / len(entries)


def last_state(entries: List[HistoryEntry]) -> Optional[JobState]:
    """Return the state of the most-recent entry, or None if empty."""
    if not entries:
        return None
    return max(entries, key=lambda e: e.recorded_at).state


def job_report(store: HistoryStore, job_id: str, limit: int = 50) -> dict:
    """Return a summary dict for a single job."""
    entries = store.get(job_id, limit=limit)
    summary = state_summary(entries)
    return {
        "job_id": job_id,
        "total_records": len(entries),
        "last_state": last_state(entries).value if last_state(entries) else None,
        "failure_rate": round(failure_rate(entries), 4),
        "state_counts": {k.value: v for k, v in summary.items()},
    }


def all_jobs_report(store: HistoryStore, limit: int = 50) -> List[dict]:
    """Return job_report dicts for every job tracked in *store*."""
    return [job_report(store, job_id, limit=limit) for job_id in store.all_job_ids()]
