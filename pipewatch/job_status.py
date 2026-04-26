"""Core data model for ETL job status tracking."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class JobState(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass
class JobStatus:
    name: str
    state: JobState
    last_run: Optional[datetime] = None
    last_success: Optional[datetime] = None
    error_message: Optional[str] = None
    stale_threshold_minutes: int = 60
    tags: list[str] = field(default_factory=list)

    def is_stale(self, now: Optional[datetime] = None) -> bool:
        """Return True if the job hasn't succeeded within the stale threshold."""
        if self.state == JobState.FAILED:
            return False  # Failed is its own category
        if self.last_success is None:
            return True
        reference = now or datetime.utcnow()
        elapsed = (reference - self.last_success).total_seconds() / 60
        return elapsed > self.stale_threshold_minutes

    def effective_state(self, now: Optional[datetime] = None) -> JobState:
        """Compute the effective state, promoting to STALE if needed."""
        if self.state == JobState.FAILED:
            return JobState.FAILED
        if self.is_stale(now):
            return JobState.STALE
        return self.state

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "effective_state": self.effective_state().value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "error_message": self.error_message,
            "stale_threshold_minutes": self.stale_threshold_minutes,
            "tags": self.tags,
        }
