"""Retention policy: prune old history entries beyond a configurable age or count."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import List, Optional

from pipewatch.history import HistoryEntry


def _utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()


@dataclass
class RetentionPolicy:
    """Defines how long or how many history entries to keep per job."""

    max_age_days: Optional[int] = None  # entries older than this are pruned
    max_entries: Optional[int] = None   # keep only the N most recent entries

    def to_dict(self) -> dict:
        return {
            "max_age_days": self.max_age_days,
            "max_entries": self.max_entries,
        }


def prune_entries(
    entries: List[HistoryEntry],
    policy: RetentionPolicy,
    now: Optional[datetime.datetime] = None,
) -> List[HistoryEntry]:
    """Return a filtered list of entries that satisfy the retention policy.

    Entries are assumed to be in arbitrary order; the function sorts by
    ``checked_at`` descending before applying ``max_entries``.
    """
    if now is None:
        now = _utcnow()

    result = list(entries)

    if policy.max_age_days is not None:
        cutoff = now - datetime.timedelta(days=policy.max_age_days)
        result = [e for e in result if e.checked_at >= cutoff]

    # Sort newest-first so max_entries keeps the most recent.
    result.sort(key=lambda e: e.checked_at, reverse=True)

    if policy.max_entries is not None:
        result = result[: policy.max_entries]

    return result


def prune_store(
    store: dict,  # job_name -> List[HistoryEntry]
    policy: RetentionPolicy,
    now: Optional[datetime.datetime] = None,
) -> dict:
    """Apply retention policy to every job in a history store mapping.

    Returns a new dict; does not mutate the input.
    """
    return {
        job: prune_entries(job_entries, policy, now=now)
        for job, job_entries in store.items()
    }
