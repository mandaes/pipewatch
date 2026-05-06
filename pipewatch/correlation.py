"""Correlate alert events across jobs to detect cascading failures."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from pipewatch.alert_rules import AlertEvent


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CorrelationGroup:
    """A cluster of alert events that fired within a time window."""

    anchor_job: str
    events: List[AlertEvent] = field(default_factory=list)
    window_seconds: int = 60

    def job_names(self) -> List[str]:
        return [e.job_name for e in self.events]

    def is_cascade(self) -> bool:
        """True when more than one distinct job appears in the group."""
        return len(set(self.job_names())) > 1

    def to_dict(self) -> Dict:
        return {
            "anchor_job": self.anchor_job,
            "job_count": len(set(self.job_names())),
            "event_count": len(self.events),
            "is_cascade": self.is_cascade(),
            "jobs": sorted(set(self.job_names())),
            "window_seconds": self.window_seconds,
        }


def correlate_events(
    events: List[AlertEvent],
    window_seconds: int = 60,
    min_group_size: int = 2,
) -> List[CorrelationGroup]:
    """Group alert events that occurred within *window_seconds* of each other.

    Events are sorted by fired_at; a new group is started whenever the gap
    between consecutive events exceeds the window.  Groups smaller than
    *min_group_size* are discarded.
    """
    if not events:
        return []

    sorted_events = sorted(events, key=lambda e: e.fired_at)
    window = timedelta(seconds=window_seconds)

    groups: List[CorrelationGroup] = []
    current: List[AlertEvent] = [sorted_events[0]]

    for evt in sorted_events[1:]:
        if evt.fired_at - current[-1].fired_at <= window:
            current.append(evt)
        else:
            if len(current) >= min_group_size:
                groups.append(
                    CorrelationGroup(
                        anchor_job=current[0].job_name,
                        events=list(current),
                        window_seconds=window_seconds,
                    )
                )
            current = [evt]

    if len(current) >= min_group_size:
        groups.append(
            CorrelationGroup(
                anchor_job=current[0].job_name,
                events=list(current),
                window_seconds=window_seconds,
            )
        )

    return groups
