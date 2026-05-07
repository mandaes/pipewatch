"""Diff two snapshots to highlight state changes between them."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from pipewatch.job_status import JobStatus, JobState, effective_state
from pipewatch.snapshot import Snapshot


@dataclass
class JobDiff:
    job_name: str
    before_state: Optional[str]
    after_state: Optional[str]
    appeared: bool = False
    disappeared: bool = False

    @property
    def changed(self) -> bool:
        return self.before_state != self.after_state

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "appeared": self.appeared,
            "disappeared": self.disappeared,
            "changed": self.changed,
        }


@dataclass
class SnapshotDiff:
    before_id: str
    after_id: str
    diffs: List[JobDiff]

    @property
    def changed_jobs(self) -> List[JobDiff]:
        return [d for d in self.diffs if d.changed]

    def to_dict(self) -> dict:
        return {
            "before_id": self.before_id,
            "after_id": self.after_id,
            "total_jobs": len(self.diffs),
            "changed_count": len(self.changed_jobs),
            "diffs": [d.to_dict() for d in self.diffs],
        }


def diff_snapshots(before: Snapshot, after: Snapshot) -> SnapshotDiff:
    """Compare two snapshots and return per-job state differences."""
    before_map: Dict[str, JobStatus] = {s.job_name: s for s in before.statuses}
    after_map: Dict[str, JobStatus] = {s.job_name: s for s in after.statuses}

    all_jobs = set(before_map) | set(after_map)
    diffs: List[JobDiff] = []

    for job in sorted(all_jobs):
        b = before_map.get(job)
        a = after_map.get(job)
        diffs.append(
            JobDiff(
                job_name=job,
                before_state=effective_state(b).value if b else None,
                after_state=effective_state(a).value if a else None,
                appeared=b is None and a is not None,
                disappeared=b is not None and a is None,
            )
        )

    return SnapshotDiff(before_id=before.snapshot_id, after_id=after.snapshot_id, diffs=diffs)
