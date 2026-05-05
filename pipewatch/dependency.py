"""Dependency tracking: detect when upstream jobs are blocking downstream ones."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pipewatch.job_status import JobState, JobStatus, effective_state


@dataclass
class DependencyRule:
    """Declares that *job* depends on all jobs listed in *requires*."""

    job: str
    requires: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"job": self.job, "requires": list(self.requires)}


@dataclass
class BlockedJob:
    """Describes a job that cannot run because an upstream dependency is unhealthy."""

    job: str
    blocked_by: str
    upstream_state: JobState

    def to_dict(self) -> dict:
        return {
            "job": self.job,
            "blocked_by": self.blocked_by,
            "upstream_state": self.upstream_state.value,
        }


def _index_statuses(statuses: List[JobStatus]) -> Dict[str, JobStatus]:
    """Build a name → JobStatus lookup from a list of statuses."""
    return {s.job_name: s for s in statuses}


def find_blocked_jobs(
    rules: List[DependencyRule],
    statuses: List[JobStatus],
    blocking_states: Optional[List[JobState]] = None,
) -> List[BlockedJob]:
    """Return every job whose upstream dependencies are in a blocking state.

    Parameters
    ----------
    rules:
        Dependency declarations to evaluate.
    statuses:
        Current snapshot of all known job statuses.
    blocking_states:
        States considered as blocking.  Defaults to FAILED and STALE.
    """
    if blocking_states is None:
        blocking_states = [JobState.FAILED, JobState.STALE]

    index = _index_statuses(statuses)
    blocked: List[BlockedJob] = []

    for rule in rules:
        for upstream_name in rule.requires:
            upstream = index.get(upstream_name)
            if upstream is None:
                # Unknown upstream treated as stale
                blocked.append(
                    BlockedJob(
                        job=rule.job,
                        blocked_by=upstream_name,
                        upstream_state=JobState.STALE,
                    )
                )
                continue

            state = effective_state(upstream)
            if state in blocking_states:
                blocked.append(
                    BlockedJob(
                        job=rule.job,
                        blocked_by=upstream_name,
                        upstream_state=state,
                    )
                )

    return blocked
