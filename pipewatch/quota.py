"""Job alert quota enforcement — limits total alerts fired per job within a time window."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class QuotaPolicy:
    max_alerts: int = 10
    window_seconds: int = 3600

    def to_dict(self) -> dict:
        return {
            "max_alerts": self.max_alerts,
            "window_seconds": self.window_seconds,
        }


@dataclass
class QuotaStore:
    path: str
    _data: Dict[str, List[str]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path) as fh:
                self._data = json.load(fh)
        else:
            self._data = {}

    def _save(self) -> None:
        with open(self.path, "w") as fh:
            json.dump(self._data, fh)

    def _prune(self, job: str, window_seconds: int) -> None:
        cutoff = (_utcnow() - timedelta(seconds=window_seconds)).isoformat()
        self._data[job] = [
            ts for ts in self._data.get(job, []) if ts >= cutoff
        ]

    def is_exceeded(self, job: str, policy: QuotaPolicy) -> bool:
        self._prune(job, policy.window_seconds)
        return len(self._data.get(job, [])) >= policy.max_alerts

    def record(self, job: str, policy: QuotaPolicy) -> bool:
        """Record an alert for *job*. Returns True if quota was not exceeded."""
        self._prune(job, policy.window_seconds)
        if len(self._data.get(job, [])) >= policy.max_alerts:
            return False
        self._data.setdefault(job, []).append(_utcnow().isoformat())
        self._save()
        return True

    def alert_count(self, job: str, policy: QuotaPolicy) -> int:
        self._prune(job, policy.window_seconds)
        return len(self._data.get(job, []))

    def reset(self, job: Optional[str] = None) -> None:
        if job is None:
            self._data = {}
        else:
            self._data.pop(job, None)
        self._save()
