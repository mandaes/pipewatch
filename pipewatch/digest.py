"""Periodic digest report: summarize pipeline health across all jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pipewatch.history import HistoryStore
from pipewatch.history_reporter import job_report
from pipewatch.trend import TrendResult, analyze_trend


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class JobDigest:
    job_name: str
    total_runs: int
    failure_rate: float
    last_state: Optional[str]
    trend: TrendResult

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "total_runs": self.total_runs,
            "failure_rate": round(self.failure_rate, 4),
            "last_state": self.last_state,
            "trend": self.trend.to_dict(),
        }


@dataclass
class DigestReport:
    generated_at: datetime = field(default_factory=_utcnow)
    jobs: List[JobDigest] = field(default_factory=list)

    @property
    def healthy_count(self) -> int:
        return sum(1 for j in self.jobs if j.failure_rate == 0.0)

    @property
    def degraded_count(self) -> int:
        return sum(1 for j in self.jobs if 0.0 < j.failure_rate < 1.0)

    @property
    def failing_count(self) -> int:
        return sum(1 for j in self.jobs if j.failure_rate == 1.0)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "summary": {
                "total_jobs": len(self.jobs),
                "healthy": self.healthy_count,
                "degraded": self.degraded_count,
                "failing": self.failing_count,
            },
            "jobs": [j.to_dict() for j in self.jobs],
        }


def build_digest(store: HistoryStore, window: int = 20) -> DigestReport:
    """Build a DigestReport from the history store.

    Args:
        store: HistoryStore instance to read history from.
        window: Number of recent entries to consider per job.
    """
    report = DigestReport()
    job_names = store.job_names()
    for name in sorted(job_names):
        entries = store.get(name, limit=window)
        jr = job_report(name, entries)
        trend = analyze_trend(entries)
        digest = JobDigest(
            job_name=name,
            total_runs=jr["total_runs"],
            failure_rate=jr["failure_rate"],
            last_state=jr["last_state"],
            trend=trend,
        )
        report.jobs.append(digest)
    return report
