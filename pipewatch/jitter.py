"""Jitter detection: flag jobs whose run duration varies erratically."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import List, Optional

from pipewatch.history import HistoryEntry


def _durations_seconds(entries: List[HistoryEntry]) -> List[float]:
    """Return completed-run durations in seconds, skipping entries without both timestamps."""
    result = []
    for e in entries:
        if e.started_at is not None and e.finished_at is not None:
            delta = (e.finished_at - e.started_at).total_seconds()
            if delta >= 0:
                result.append(delta)
    return result


@dataclass
class JitterResult:
    job_name: str
    mean_seconds: float
    stddev_seconds: float
    cv: float          # coefficient of variation  (stddev / mean)
    is_jittery: bool
    sample_count: int

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "mean_seconds": round(self.mean_seconds, 3),
            "stddev_seconds": round(self.stddev_seconds, 3),
            "cv": round(self.cv, 4),
            "is_jittery": self.is_jittery,
            "sample_count": self.sample_count,
        }


def detect_jitter(
    job_name: str,
    entries: List[HistoryEntry],
    *,
    min_samples: int = 5,
    cv_threshold: float = 0.5,
) -> Optional[JitterResult]:
    """Analyse duration variance for *job_name*.

    Returns ``None`` when there are fewer than *min_samples* completed runs.
    Sets ``is_jittery=True`` when the coefficient of variation exceeds
    *cv_threshold* (default 0.5, i.e. 50 %).
    """
    durations = _durations_seconds(entries)
    if len(durations) < min_samples:
        return None

    mean = statistics.mean(durations)
    if mean == 0:
        return JitterResult(
            job_name=job_name,
            mean_seconds=0.0,
            stddev_seconds=0.0,
            cv=0.0,
            is_jittery=False,
            sample_count=len(durations),
        )

    stddev = statistics.stdev(durations)
    cv = stddev / mean

    return JitterResult(
        job_name=job_name,
        mean_seconds=mean,
        stddev_seconds=stddev,
        cv=cv,
        is_jittery=cv > cv_threshold,
        sample_count=len(durations),
    )
