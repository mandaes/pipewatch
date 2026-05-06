"""Heartbeat tracker — detects jobs that have stopped reporting entirely."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class HeartbeatRecord:
    job_name: str
    last_seen: datetime
    expected_interval_seconds: int

    def is_missing(self, now: Optional[datetime] = None) -> bool:
        """Return True when the job has not reported within its expected interval."""
        now = now or _utcnow()
        elapsed = (now - self.last_seen).total_seconds()
        return elapsed > self.expected_interval_seconds

    def seconds_overdue(self, now: Optional[datetime] = None) -> float:
        """Seconds past the expected interval (negative means still on time)."""
        now = now or _utcnow()
        elapsed = (now - self.last_seen).total_seconds()
        return elapsed - self.expected_interval_seconds

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "last_seen": self.last_seen.isoformat(),
            "expected_interval_seconds": self.expected_interval_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HeartbeatRecord":
        return cls(
            job_name=data["job_name"],
            last_seen=datetime.fromisoformat(data["last_seen"]),
            expected_interval_seconds=int(data["expected_interval_seconds"]),
        )


@dataclass
class HeartbeatStore:
    path: str
    _records: Dict[str, HeartbeatRecord] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            self._records = {
                k: HeartbeatRecord.from_dict(v) for k, v in raw.items()
            }

    def _save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({k: v.to_dict() for k, v in self._records.items()}, fh, indent=2)

    def touch(self, job_name: str, expected_interval_seconds: int) -> HeartbeatRecord:
        """Record that *job_name* is alive right now."""
        record = HeartbeatRecord(
            job_name=job_name,
            last_seen=_utcnow(),
            expected_interval_seconds=expected_interval_seconds,
        )
        self._records[job_name] = record
        self._save()
        return record

    def get(self, job_name: str) -> Optional[HeartbeatRecord]:
        return self._records.get(job_name)

    def missing_jobs(self, now: Optional[datetime] = None) -> List[HeartbeatRecord]:
        """Return all records whose heartbeat is overdue."""
        return [r for r in self._records.values() if r.is_missing(now=now)]

    def all_records(self) -> List[HeartbeatRecord]:
        return list(self._records.values())
