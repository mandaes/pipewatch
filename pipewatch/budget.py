"""Alert budget tracking — limits how many alerts fire per job per time window."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class BudgetPolicy:
    """Defines the maximum number of alerts allowed in a rolling window."""
    max_alerts: int = 10
    window_seconds: int = 3600  # 1 hour

    def to_dict(self) -> dict:
        return {
            "max_alerts": self.max_alerts,
            "window_seconds": self.window_seconds,
        }


@dataclass
class BudgetStore:
    path: str
    _data: Dict[str, List[str]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r") as fh:
                self._data = json.load(fh)
        else:
            self._data = {}

    def _save(self) -> None:
        with open(self.path, "w") as fh:
            json.dump(self._data, fh)

    def _prune(self, job: str, window_seconds: int) -> None:
        now = _utcnow()
        timestamps = self._data.get(job, [])
        cutoff = now.timestamp() - window_seconds
        self._data[job] = [t for t in timestamps if float(t) > cutoff]

    def record_alert(self, job: str) -> None:
        """Record that an alert fired for *job* right now."""
        self._data.setdefault(job, []).append(str(_utcnow().timestamp()))
        self._save()

    def alert_count(self, job: str, window_seconds: int) -> int:
        """Return the number of alerts fired for *job* within the window."""
        self._prune(job, window_seconds)
        return len(self._data.get(job, []))

    def is_exhausted(self, job: str, policy: BudgetPolicy) -> bool:
        """Return True when the alert budget for *job* is used up."""
        return self.alert_count(job, policy.window_seconds) >= policy.max_alerts

    def remaining(self, job: str, policy: BudgetPolicy) -> int:
        """Return how many alerts remain in the current window for *job*."""
        used = self.alert_count(job, policy.window_seconds)
        return max(0, policy.max_alerts - used)

    def reset(self, job: str) -> None:
        """Clear the alert history for *job*."""
        self._data.pop(job, None)
        self._save()
