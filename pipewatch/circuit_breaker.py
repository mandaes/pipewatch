"""Circuit breaker for pipeline jobs — trips after N consecutive failures."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BreakerState(str, Enum):
    CLOSED = "closed"      # normal — alerts flow through
    OPEN = "open"          # tripped — alerts suppressed
    HALF_OPEN = "half_open"  # testing recovery


@dataclass
class CircuitBreakerPolicy:
    """Configuration for a circuit breaker."""
    failure_threshold: int = 3       # consecutive failures to trip
    recovery_window_seconds: int = 300  # seconds before moving to HALF_OPEN
    success_threshold: int = 1       # successes in HALF_OPEN to close again

    def to_dict(self) -> dict:
        return {
            "failure_threshold": self.failure_threshold,
            "recovery_window_seconds": self.recovery_window_seconds,
            "success_threshold": self.success_threshold,
        }


@dataclass
class BreakerRecord:
    """Per-job breaker state persisted to disk."""
    job: str
    state: BreakerState = BreakerState.CLOSED
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    tripped_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "job": self.job,
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "tripped_at": self.tripped_at.isoformat() if self.tripped_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BreakerRecord":
        tripped_at = None
        if data.get("tripped_at"):
            tripped_at = datetime.fromisoformat(data["tripped_at"])
        return cls(
            job=data["job"],
            state=BreakerState(data.get("state", BreakerState.CLOSED)),
            consecutive_failures=data.get("consecutive_failures", 0),
            consecutive_successes=data.get("consecutive_successes", 0),
            tripped_at=tripped_at,
        )


class CircuitBreakerStore:
    """Loads and persists breaker records from a JSON file."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._records: Dict[str, BreakerRecord] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._path):
            with open(self._path) as fh:
                raw = json.load(fh)
            self._records = {k: BreakerRecord.from_dict(v) for k, v in raw.items()}

    def _save(self) -> None:
        with open(self._path, "w") as fh:
            json.dump({k: v.to_dict() for k, v in self._records.items()}, fh, indent=2)

    def get(self, job: str) -> BreakerRecord:
        return self._records.get(job, BreakerRecord(job=job))

    def record_failure(self, job: str, policy: CircuitBreakerPolicy) -> BreakerRecord:
        rec = self.get(job)
        now = _utcnow()
        if rec.state == BreakerState.OPEN:
            elapsed = (now - rec.tripped_at).total_seconds() if rec.tripped_at else 0
            if elapsed >= policy.recovery_window_seconds:
                rec.state = BreakerState.HALF_OPEN
                rec.consecutive_successes = 0
        rec.consecutive_failures += 1
        rec.consecutive_successes = 0
        if rec.state in (BreakerState.CLOSED, BreakerState.HALF_OPEN):
            if rec.consecutive_failures >= policy.failure_threshold:
                rec.state = BreakerState.OPEN
                rec.tripped_at = now
        self._records[job] = rec
        self._save()
        return rec

    def record_success(self, job: str, policy: CircuitBreakerPolicy) -> BreakerRecord:
        rec = self.get(job)
        rec.consecutive_failures = 0
        if rec.state == BreakerState.OPEN:
            now = _utcnow()
            elapsed = (now - rec.tripped_at).total_seconds() if rec.tripped_at else 0
            if elapsed >= policy.recovery_window_seconds:
                rec.state = BreakerState.HALF_OPEN
                rec.consecutive_successes = 0
        if rec.state == BreakerState.HALF_OPEN:
            rec.consecutive_successes += 1
            if rec.consecutive_successes >= policy.success_threshold:
                rec.state = BreakerState.CLOSED
                rec.tripped_at = None
        self._records[job] = rec
        self._save()
        return rec

    def is_open(self, job: str, policy: CircuitBreakerPolicy) -> bool:
        rec = self.get(job)
        if rec.state != BreakerState.OPEN:
            return False
        if rec.tripped_at is None:
            return True
        elapsed = (_utcnow() - rec.tripped_at).total_seconds()
        return elapsed < policy.recovery_window_seconds

    def all_records(self) -> List[BreakerRecord]:
        return list(self._records.values())
