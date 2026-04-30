"""Silencer: suppress alerts for specific jobs/states within a time window."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from pipewatch.alert_rules import AlertEvent


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SilenceRule:
    job_name: str  # exact match or "*" for all jobs
    reason: str
    until: datetime  # UTC
    states: List[str] = field(default_factory=list)  # empty = all states

    def is_active(self, now: Optional[datetime] = None) -> bool:
        now = now or _utcnow()
        return now < self.until

    def suppresses(self, event: AlertEvent, now: Optional[datetime] = None) -> bool:
        if not self.is_active(now):
            return False
        if self.job_name != "*" and self.job_name != event.job_name:
            return False
        if self.states and event.state not in self.states:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "reason": self.reason,
            "until": self.until.isoformat(),
            "states": self.states,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SilenceRule":
        return cls(
            job_name=data["job_name"],
            reason=data["reason"],
            until=datetime.fromisoformat(data["until"]),
            states=data.get("states", []),
        )


def filter_silenced(
    events: List[AlertEvent],
    rules: List[SilenceRule],
    now: Optional[datetime] = None,
) -> List[AlertEvent]:
    """Return only events not suppressed by any active silence rule."""
    return [
        e for e in events
        if not any(r.suppresses(e, now) for r in rules)
    ]


def load_silence_rules(path: str) -> List[SilenceRule]:
    if not os.path.exists(path):
        return []
    with open(path, "r") as fh:
        data = json.load(fh)
    return [SilenceRule.from_dict(d) for d in data]


def save_silence_rules(rules: List[SilenceRule], path: str) -> None:
    with open(path, "w") as fh:
        json.dump([r.to_dict() for r in rules], fh, indent=2)
