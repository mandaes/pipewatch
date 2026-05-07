"""Replay historical job events for testing alert rules and notifiers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from pipewatch.alert_rules import AlertEvent, AlertRule, evaluate_rules
from pipewatch.history import HistoryEntry
from pipewatch.job_status import JobStatus, JobState, effective_state


def _entry_to_status(entry: HistoryEntry) -> JobStatus:
    """Convert a HistoryEntry into a JobStatus for rule evaluation."""
    return JobStatus(
        job_name=entry.job_name,
        last_success=entry.finished_at if entry.state == JobState.SUCCESS else None,
        last_run=entry.finished_at,
        stale_threshold_seconds=None,
        tags=entry.tags,
    )


@dataclass
class ReplayResult:
    """Outcome of replaying a sequence of history entries."""

    total_entries: int
    matched_events: List[AlertEvent] = field(default_factory=list)
    skipped_jobs: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_entries": self.total_entries,
            "matched_count": len(self.matched_events),
            "skipped_jobs": sorted(set(self.skipped_jobs)),
            "events": [e.to_dict() for e in self.matched_events],
        }


def replay(
    entries: List[HistoryEntry],
    rules: List[AlertRule],
    job_filter: Optional[List[str]] = None,
) -> ReplayResult:
    """Replay *entries* against *rules* and return all matched events.

    Args:
        entries: Ordered list of history entries to replay.
        rules: Alert rules to evaluate against each entry.
        job_filter: Optional list of job names to include; others are skipped.

    Returns:
        A :class:`ReplayResult` summarising matched events.
    """
    result = ReplayResult(total_entries=len(entries))

    for entry in entries:
        if job_filter is not None and entry.job_name not in job_filter:
            result.skipped_jobs.append(entry.job_name)
            continue

        status = _entry_to_status(entry)
        events = evaluate_rules(rules, [status])
        result.matched_events.extend(events)

    return result
