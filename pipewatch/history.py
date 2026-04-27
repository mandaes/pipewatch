"""Persistent history store for job poll results using a simple JSON log."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

DEFAULT_HISTORY_PATH = Path(".pipewatch_history.jsonl")
MAX_ENTRIES_PER_JOB = 100


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HistoryEntry:
    """A single recorded snapshot of a job's status."""

    def __init__(self, job_name: str, state: str, last_success: Optional[str], recorded_at: Optional[str] = None):
        self.job_name = job_name
        self.state = state
        self.last_success = last_success
        self.recorded_at: str = recorded_at or _utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "state": self.state,
            "last_success": self.last_success,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        return cls(
            job_name=data["job_name"],
            state=data["state"],
            last_success=data.get("last_success"),
            recorded_at=data.get("recorded_at"),
        )


class HistoryStore:
    """Append-only JSONL history store for job status entries."""

    def __init__(self, path: Path = DEFAULT_HISTORY_PATH):
        self.path = Path(path)

    def append(self, entry: HistoryEntry) -> None:
        """Append a single entry to the history file."""
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict()) + "\n")

    def read_all(self) -> List[HistoryEntry]:
        """Read all entries from the history file."""
        if not self.path.exists():
            return []
        entries: List[HistoryEntry] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        entries.append(HistoryEntry.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, KeyError):
                        continue
        return entries

    def recent_for_job(self, job_name: str, limit: int = MAX_ENTRIES_PER_JOB) -> List[HistoryEntry]:
        """Return the most recent entries for a specific job."""
        all_entries = self.read_all()
        job_entries = [e for e in all_entries if e.job_name == job_name]
        return job_entries[-limit:]

    def clear(self) -> None:
        """Delete the history file."""
        if self.path.exists():
            os.remove(self.path)
