"""Exponential back-off policy for alert re-notification.

When a job stays in a failed/stale state across multiple poll cycles the
notifier should not fire on every single cycle.  A BackoffPolicy decides
whether enough time has elapsed since the last notification before another
one is permitted.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class BackoffPolicy:
    """Configuration for exponential back-off."""

    base_seconds: float = 60.0
    multiplier: float = 2.0
    max_seconds: float = 3600.0
    max_attempts: Optional[int] = None

    def delay_for_attempt(self, attempt: int) -> float:
        """Return the required quiet-period (seconds) before attempt *attempt*.

        *attempt* is 1-based: the first retry is attempt=1.
        """
        if attempt <= 0:
            return 0.0
        raw = self.base_seconds * math.pow(self.multiplier, attempt - 1)
        return min(raw, self.max_seconds)

    def to_dict(self) -> dict:
        return {
            "base_seconds": self.base_seconds,
            "multiplier": self.multiplier,
            "max_seconds": self.max_seconds,
            "max_attempts": self.max_attempts,
        }


@dataclass
class BackoffState:
    """Per-job mutable state tracked by BackoffStore."""

    job_name: str
    attempt: int = 0
    last_notified_at: Optional[datetime] = None

    def should_notify(self, policy: BackoffPolicy, now: Optional[datetime] = None) -> bool:
        now = now or _utcnow()
        if policy.max_attempts is not None and self.attempt >= policy.max_attempts:
            return False
        if self.last_notified_at is None:
            return True
        elapsed = (now - self.last_notified_at).total_seconds()
        return elapsed >= policy.delay_for_attempt(self.attempt)

    def record_notification(self, now: Optional[datetime] = None) -> None:
        self.attempt += 1
        self.last_notified_at = now or _utcnow()

    def reset(self) -> None:
        self.attempt = 0
        self.last_notified_at = None


class BackoffStore:
    """Persist BackoffState records to a JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: Dict[str, dict] = self._load()

    def _load(self) -> Dict[str, dict]:
        if self._path.exists():
            return json.loads(self._path.read_text())
        return {}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, default=str))

    def get(self, job_name: str) -> BackoffState:
        raw = self._data.get(job_name)
        if raw is None:
            return BackoffState(job_name=job_name)
        return BackoffState(
            job_name=job_name,
            attempt=raw.get("attempt", 0),
            last_notified_at=(
                datetime.fromisoformat(raw["last_notified_at"])
                if raw.get("last_notified_at")
                else None
            ),
        )

    def save_state(self, state: BackoffState) -> None:
        self._data[state.job_name] = {
            "attempt": state.attempt,
            "last_notified_at": (
                state.last_notified_at.isoformat() if state.last_notified_at else None
            ),
        }
        self._save()

    def remove(self, job_name: str) -> None:
        self._data.pop(job_name, None)
        self._save()
