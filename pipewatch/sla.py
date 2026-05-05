"""SLA (Service Level Agreement) tracking for pipeline jobs.

Defines expected completion windows for jobs and detects violations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from pipewatch.job_status import JobStatus, JobState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SLAPolicy:
    """Defines an SLA window for a named job."""
    job_name: str
    max_duration_seconds: Optional[float] = None  # max runtime before violation
    must_succeed_within_seconds: Optional[float] = None  # must complete OK within window

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "max_duration_seconds": self.max_duration_seconds,
            "must_succeed_within_seconds": self.must_succeed_within_seconds,
        }


@dataclass
class SLAViolation:
    """Represents a detected SLA violation for a job."""
    job_name: str
    reason: str
    checked_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "reason": self.reason,
            "checked_at": self.checked_at.isoformat(),
        }


def check_sla(policy: SLAPolicy, status: JobStatus, now: Optional[datetime] = None) -> Optional[SLAViolation]:
    """Check a single JobStatus against an SLAPolicy.

    Returns an SLAViolation if a breach is detected, otherwise None.
    """
    if status.job_name != policy.job_name:
        return None

    if now is None:
        now = _utcnow()

    if policy.max_duration_seconds is not None and status.duration_seconds is not None:
        if status.duration_seconds > policy.max_duration_seconds:
            return SLAViolation(
                job_name=status.job_name,
                reason=(
                    f"duration {status.duration_seconds:.1f}s exceeds "
                    f"SLA max of {policy.max_duration_seconds:.1f}s"
                ),
                checked_at=now,
            )

    if policy.must_succeed_within_seconds is not None and status.last_success is not None:
        age = (now - status.last_success).total_seconds()
        if age > policy.must_succeed_within_seconds:
            return SLAViolation(
                job_name=status.job_name,
                reason=(
                    f"last success was {age:.0f}s ago, "
                    f"SLA requires success within {policy.must_succeed_within_seconds:.0f}s"
                ),
                checked_at=now,
            )

    return None


def evaluate_slas(
    policies: List[SLAPolicy],
    statuses: List[JobStatus],
    now: Optional[datetime] = None,
) -> List[SLAViolation]:
    """Evaluate all SLA policies against the provided job statuses."""
    index = {s.job_name: s for s in statuses}
    violations: List[SLAViolation] = []
    for policy in policies:
        status = index.get(policy.job_name)
        if status is None:
            continue
        violation = check_sla(policy, status, now=now)
        if violation is not None:
            violations.append(violation)
    return violations
