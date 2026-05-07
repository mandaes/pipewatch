"""Tests for pipewatch.snapshot_diff module."""
from __future__ import annotations

from datetime import datetime, timezone

from pipewatch.job_status import JobState, JobStatus
from pipewatch.snapshot import Snapshot
from pipewatch.snapshot_diff import diff_snapshots, JobDiff, SnapshotDiff


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_status(name: str, state: JobState = JobState.SUCCESS) -> JobStatus:
    return JobStatus(
        job_name=name,
        state=state,
        last_success=_now(),
        last_run=_now(),
        stale_threshold_seconds=3600,
        tags={},
    )


def make_snapshot(statuses, snap_id="snap-a") -> Snapshot:
    return Snapshot(snapshot_id=snap_id, taken_at=_now(), statuses=statuses)


class TestJobDiff:
    def test_changed_when_states_differ(self):
        d = JobDiff(job_name="j", before_state="success", after_state="failed")
        assert d.changed is True

    def test_not_changed_when_states_same(self):
        d = JobDiff(job_name="j", before_state="success", after_state="success")
        assert d.changed is False

    def test_to_dict_contains_required_keys(self):
        d = JobDiff(job_name="j", before_state="success", after_state="failed")
        result = d.to_dict()
        for key in ("job_name", "before_state", "after_state", "appeared", "disappeared", "changed"):
            assert key in result


class TestDiffSnapshots:
    def test_no_changes_returns_empty_changed(self):
        s = [make_status("job_a"), make_status("job_b")]
        before = make_snapshot(s, "id-1")
        after = make_snapshot(s, "id-2")
        diff = diff_snapshots(before, after)
        assert diff.changed_jobs == []

    def test_detects_state_change(self):
        before = make_snapshot([make_status("job_a", JobState.SUCCESS)], "id-1")
        after = make_snapshot([make_status("job_a", JobState.FAILED)], "id-2")
        diff = diff_snapshots(before, after)
        assert len(diff.changed_jobs) == 1
        assert diff.changed_jobs[0].job_name == "job_a"
        assert diff.changed_jobs[0].before_state == "success"
        assert diff.changed_jobs[0].after_state == "failed"

    def test_detects_new_job(self):
        before = make_snapshot([], "id-1")
        after = make_snapshot([make_status("new_job")], "id-2")
        diff = diff_snapshots(before, after)
        assert len(diff.changed_jobs) == 1
        assert diff.changed_jobs[0].appeared is True

    def test_detects_disappeared_job(self):
        before = make_snapshot([make_status("old_job")], "id-1")
        after = make_snapshot([], "id-2")
        diff = diff_snapshots(before, after)
        assert len(diff.changed_jobs) == 1
        assert diff.changed_jobs[0].disappeared is True

    def test_to_dict_contains_required_keys(self):
        before = make_snapshot([make_status("job_a")], "id-1")
        after = make_snapshot([make_status("job_a", JobState.FAILED)], "id-2")
        result = diff_snapshots(before, after).to_dict()
        for key in ("before_id", "after_id", "total_jobs", "changed_count", "diffs"):
            assert key in result

    def test_diffs_sorted_by_job_name(self):
        before = make_snapshot([make_status("z_job"), make_status("a_job")], "id-1")
        after = make_snapshot([make_status("z_job"), make_status("a_job")], "id-2")
        diff = diff_snapshots(before, after)
        names = [d.job_name for d in diff.diffs]
        assert names == sorted(names)
