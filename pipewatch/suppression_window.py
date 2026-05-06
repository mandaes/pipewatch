"""Suppression window: skip alerting during scheduled maintenance periods."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SuppressionWindow:
    """A named time window during which alerts are suppressed for matching jobs."""

    name: str
    start: datetime
    end: datetime
    job_names: List[str] = field(default_factory=list)  # empty = all jobs

    def is_active(self, now: Optional[datetime] = None) -> bool:
        """Return True if the window is currently active."""
        now = now or _utcnow()
        return self.start <= now <= self.end

    def suppresses(self, job_name: str, now: Optional[datetime] = None) -> bool:
        """Return True if this window suppresses alerts for *job_name* right now."""
        if not self.is_active(now):
            return False
        if not self.job_names:
            return True
        return job_name in self.job_names

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "job_names": list(self.job_names),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SuppressionWindow":
        return cls(
            name=data["name"],
            start=datetime.fromisoformat(data["start"]),
            end=datetime.fromisoformat(data["end"]),
            job_names=data.get("job_names", []),
        )


class SuppressionWindowStore:
    """Persist suppression windows to a JSON file."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def _load(self) -> List[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text())

    def _save(self, records: List[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(records, indent=2))

    def all(self) -> List[SuppressionWindow]:
        return [SuppressionWindow.from_dict(r) for r in self._load()]

    def add(self, window: SuppressionWindow) -> None:
        records = self._load()
        records.append(window.to_dict())
        self._save(records)

    def remove(self, name: str) -> bool:
        records = self._load()
        new_records = [r for r in records if r["name"] != name]
        if len(new_records) == len(records):
            return False
        self._save(new_records)
        return True

    def is_suppressed(self, job_name: str, now: Optional[datetime] = None) -> bool:
        """Return True if any active window suppresses *job_name*."""
        return any(w.suppresses(job_name, now) for w in self.all())
