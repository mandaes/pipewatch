"""Cooldown tracking: suppress repeated alerts for the same job within a time window."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CooldownPolicy:
    """Defines how long to suppress repeated alerts after one fires."""

    window_seconds: int = 300  # default: 5 minutes

    def to_dict(self) -> dict:
        return {"window_seconds": self.window_seconds}


@dataclass
class CooldownStore:
    """Persists the last-alerted timestamps per job+state key."""

    path: str
    _data: Dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as fh:
                self._data = json.load(fh)
        else:
            self._data = {}

    def _save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh)

    def _key(self, job_name: str, state: str) -> str:
        return f"{job_name}::{state}"

    def last_alerted(self, job_name: str, state: str) -> Optional[datetime]:
        """Return the last alert timestamp for a job+state pair, or None."""
        raw = self._data.get(self._key(job_name, state))
        if raw is None:
            return None
        return datetime.fromisoformat(raw)

    def is_cooling_down(
        self, job_name: str, state: str, policy: CooldownPolicy
    ) -> bool:
        """Return True if the job+state is still within its cooldown window."""
        last = self.last_alerted(job_name, state)
        if last is None:
            return False
        elapsed = (_utcnow() - last).total_seconds()
        return elapsed < policy.window_seconds

    def record_alert(self, job_name: str, state: str) -> None:
        """Record that an alert was just sent for this job+state."""
        self._data[self._key(job_name, state)] = _utcnow().isoformat()
        self._save()

    def clear(self, job_name: str, state: str) -> None:
        """Remove the cooldown entry for a job+state pair."""
        key = self._key(job_name, state)
        if key in self._data:
            del self._data[key]
            self._save()
