"""Checkpoint tracking: record and compare pipeline progress markers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Checkpoint:
    job_name: str
    marker: str  # e.g. last processed timestamp, batch ID, offset
    recorded_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "marker": self.marker,
            "recorded_at": self.recorded_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(
            job_name=data["job_name"],
            marker=data["marker"],
            recorded_at=datetime.fromisoformat(data["recorded_at"]),
        )


class CheckpointStore:
    """Persist and retrieve the latest checkpoint per job."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    def save(self, checkpoint: Checkpoint) -> None:
        self._data[checkpoint.job_name] = checkpoint.to_dict()
        self._save()

    def get(self, job_name: str) -> Optional[Checkpoint]:
        entry = self._data.get(job_name)
        if entry is None:
            return None
        return Checkpoint.from_dict(entry)

    def all(self) -> list[Checkpoint]:
        return [Checkpoint.from_dict(v) for v in self._data.values()]

    def delete(self, job_name: str) -> bool:
        if job_name in self._data:
            del self._data[job_name]
            self._save()
            return True
        return False


def is_regressed(previous: Checkpoint, current: Checkpoint) -> bool:
    """Return True if the current marker appears older than the previous one.

    Comparison is lexicographic, which works for ISO timestamps and
    zero-padded numeric IDs.  Callers that use non-comparable markers
    should implement their own logic.
    """
    return current.marker < previous.marker
