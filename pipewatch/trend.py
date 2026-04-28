"""Trend analysis for job history: detects improving, degrading, or stable patterns."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List

from pipewatch.history import HistoryEntry
from pipewatch.job_status import JobState


class TrendDirection(str, Enum):
    IMPROVING = "improving"
    DEGRADING = "degrading"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class TrendResult:
    job_name: str
    direction: TrendDirection
    failure_rate_recent: float
    failure_rate_older: float
    sample_size: int

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "direction": self.direction.value,
            "failure_rate_recent": round(self.failure_rate_recent, 4),
            "failure_rate_older": round(self.failure_rate_older, 4),
            "sample_size": self.sample_size,
        }


def _failure_rate(entries: List[HistoryEntry]) -> float:
    """Return fraction of entries that are in a failed state."""
    if not entries:
        return 0.0
    failed = sum(
        1 for e in entries if e.state in (JobState.FAILED, JobState.STALE)
    )
    return failed / len(entries)


def analyze_trend(
    job_name: str,
    entries: List[HistoryEntry],
    min_samples: int = 6,
    threshold: float = 0.15,
) -> TrendResult:
    """Split history in half and compare failure rates to detect trend direction.

    Args:
        job_name: Name of the job being analysed.
        entries: Chronologically ordered history entries (oldest first).
        min_samples: Minimum number of entries required to compute a trend.
        threshold: Minimum absolute difference in failure rate to flag a direction.
    """
    if len(entries) < min_samples:
        return TrendResult(
            job_name=job_name,
            direction=TrendDirection.INSUFFICIENT_DATA,
            failure_rate_recent=0.0,
            failure_rate_older=0.0,
            sample_size=len(entries),
        )

    mid = len(entries) // 2
    older = entries[:mid]
    recent = entries[mid:]

    rate_older = _failure_rate(older)
    rate_recent = _failure_rate(recent)
    delta = rate_recent - rate_older

    if delta > threshold:
        direction = TrendDirection.DEGRADING
    elif delta < -threshold:
        direction = TrendDirection.IMPROVING
    else:
        direction = TrendDirection.STABLE

    return TrendResult(
        job_name=job_name,
        direction=direction,
        failure_rate_recent=rate_recent,
        failure_rate_older=rate_older,
        sample_size=len(entries),
    )
