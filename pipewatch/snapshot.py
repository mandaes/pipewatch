"""Point-in-time snapshot of all job statuses for diffing and auditing."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from pipewatch.job_status import JobStatus, to_dict as status_to_dict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Snapshot:
    snapshot_id: str
    taken_at: datetime
    statuses: List[JobStatus]
    label: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "taken_at": self.taken_at.isoformat(),
            "label": self.label,
            "statuses": [status_to_dict(s) for s in self.statuses],
        }

    @staticmethod
    def from_dict(data: dict) -> "Snapshot":
        from pipewatch.job_status import JobState

        statuses = [
            JobStatus(
                job_name=s["job_name"],
                state=JobState(s["state"]),
                last_success=datetime.fromisoformat(s["last_success"]) if s.get("last_success") else None,
                last_run=datetime.fromisoformat(s["last_run"]) if s.get("last_run") else None,
                stale_threshold_seconds=s.get("stale_threshold_seconds", 3600),
                tags=s.get("tags", {}),
            )
            for s in data.get("statuses", [])
        ]
        return Snapshot(
            snapshot_id=data["snapshot_id"],
            taken_at=datetime.fromisoformat(data["taken_at"]),
            statuses=statuses,
            label=data.get("label"),
        )


class SnapshotStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: List[dict] = self._load()

    def _load(self) -> List[dict]:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return []

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._entries, indent=2))

    def save_snapshot(self, statuses: List[JobStatus], label: Optional[str] = None) -> Snapshot:
        snap = Snapshot(
            snapshot_id=str(uuid.uuid4()),
            taken_at=_utcnow(),
            statuses=statuses,
            label=label,
        )
        self._entries.append(snap.to_dict())
        self._save()
        return snap

    def list_snapshots(self) -> List[Snapshot]:
        return [Snapshot.from_dict(e) for e in self._entries]

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        for e in self._entries:
            if e["snapshot_id"] == snapshot_id:
                return Snapshot.from_dict(e)
        return None

    def delete_snapshot(self, snapshot_id: str) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e["snapshot_id"] != snapshot_id]
        if len(self._entries) < before:
            self._save()
            return True
        return False
