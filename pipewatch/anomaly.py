"""Anomaly detection for pipeline job durations and failure spikes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from pipewatch.history import HistoryEntry
from pipewatch.job_status import JobState


class AnomalyKind(str, Enum):
    DURATION_SPIKE = "duration_spike"
    FAILURE_SPIKE = "failure_spike"
    NO_RUNS = "no_runs"


@dataclass
class AnomalyResult:
    job_name: str
    kind: AnomalyKind
    detail: str
    score: float  # 0.0 – 1.0, higher means more anomalous

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "kind": self.kind.value,
            "detail": self.detail,
            "score": round(self.score, 4),
        }


def _durations_seconds(entries: List[HistoryEntry]) -> List[float]:
    """Return run durations in seconds for entries that have both timestamps."""
    durations = []
    for e in entries:
        if e.started_at and e.finished_at:
            delta = (e.finished_at - e.started_at).total_seconds()
            if delta >= 0:
                durations.append(delta)
    return durations


def detect_duration_spike(
    job_name: str,
    entries: List[HistoryEntry],
    z_threshold: float = 2.5,
) -> Optional[AnomalyResult]:
    """Flag the most recent run if its duration is a z-score outlier."""
    durations = _durations_seconds(entries)
    if len(durations) < 3:
        return None
    mean = sum(durations) / len(durations)
    variance = sum((d - mean) ** 2 for d in durations) / len(durations)
    std = variance ** 0.5
    if std == 0:
        return None
    latest = durations[-1]
    z = (latest - mean) / std
    if z > z_threshold:
        score = min(z / (z_threshold * 2), 1.0)
        return AnomalyResult(
            job_name=job_name,
            kind=AnomalyKind.DURATION_SPIKE,
            detail=f"Latest duration {latest:.1f}s is {z:.2f} std-devs above mean {mean:.1f}s",
            score=score,
        )
    return None


def detect_failure_spike(
    job_name: str,
    entries: List[HistoryEntry],
    window: int = 5,
    threshold: float = 0.6,
) -> Optional[AnomalyResult]:
    """Flag if failure rate in the last *window* runs exceeds *threshold*."""
    recent = entries[-window:]
    if not recent:
        return None
    failures = sum(1 for e in recent if e.state == JobState.FAILED)
    rate = failures / len(recent)
    if rate >= threshold:
        score = min(rate, 1.0)
        return AnomalyResult(
            job_name=job_name,
            kind=AnomalyKind.FAILURE_SPIKE,
            detail=f"{failures}/{len(recent)} recent runs failed (rate={rate:.0%})",
            score=score,
        )
    return None


def analyze_anomalies(
    job_name: str,
    entries: List[HistoryEntry],
    z_threshold: float = 2.5,
    failure_window: int = 5,
    failure_threshold: float = 0.6,
) -> List[AnomalyResult]:
    """Run all anomaly detectors and return every triggered result."""
    if not entries:
        return [
            AnomalyResult(
                job_name=job_name,
                kind=AnomalyKind.NO_RUNS,
                detail="No history entries found for job",
                score=1.0,
            )
        ]
    results: List[AnomalyResult] = []
    spike = detect_duration_spike(job_name, entries, z_threshold)
    if spike:
        results.append(spike)
    fscore = detect_failure_spike(job_name, entries, failure_window, failure_threshold)
    if fscore:
        results.append(fscore)
    return results
