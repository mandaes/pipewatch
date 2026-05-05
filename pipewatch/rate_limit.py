"""Rate limiting for alert notifications to prevent alert storms."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RateLimitPolicy:
    """Defines how frequently alerts for a given job/rule may fire."""

    max_alerts: int = 3
    window_seconds: int = 3600

    def to_dict(self) -> dict:
        return {
            "max_alerts": self.max_alerts,
            "window_seconds": self.window_seconds,
        }


@dataclass
class RateLimitStore:
    """Tracks alert counts per (job_name, rule_name) key within a sliding window."""

    path: str
    _data: Dict[str, list] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r") as fh:
                raw = json.load(fh)
            self._data = {k: v for k, v in raw.items()}
        else:
            self._data = {}

    def _save(self) -> None:
        with open(self.path, "w") as fh:
            json.dump(self._data, fh)

    @staticmethod
    def _key(job_name: str, rule_name: str) -> str:
        return f"{job_name}::{rule_name}"

    def _prune(self, key: str, window_seconds: int, now: datetime) -> None:
        cutoff = now.timestamp() - window_seconds
        self._data[key] = [
            ts for ts in self._data.get(key, []) if ts > cutoff
        ]

    def is_allowed(
        self,
        job_name: str,
        rule_name: str,
        policy: RateLimitPolicy,
        now: Optional[datetime] = None,
    ) -> bool:
        """Return True if the alert is within the allowed rate."""
        if now is None:
            now = _utcnow()
        key = self._key(job_name, rule_name)
        self._prune(key, policy.window_seconds, now)
        return len(self._data.get(key, [])) < policy.max_alerts

    def record(
        self,
        job_name: str,
        rule_name: str,
        now: Optional[datetime] = None,
    ) -> None:
        """Record that an alert fired right now."""
        if now is None:
            now = _utcnow()
        key = self._key(job_name, rule_name)
        self._data.setdefault(key, []).append(now.timestamp())
        self._save()

    def count(
        self,
        job_name: str,
        rule_name: str,
        policy: RateLimitPolicy,
        now: Optional[datetime] = None,
    ) -> int:
        """Return the number of alerts recorded within the current window."""
        if now is None:
            now = _utcnow()
        key = self._key(job_name, rule_name)
        self._prune(key, policy.window_seconds, now)
        return len(self._data.get(key, []))
