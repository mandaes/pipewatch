"""Tests for pipewatch.snapshot module."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipewatch.job_status import JobState, JobStatus
from pipewatch.snapshot import Snapshot, SnapshotStore


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


class TestSnapshotToDict:
    def test_contains_required_keys(self):
        snap = Snapshot(
            snapshot_id="abc-123",
            taken_at=_now(),
            statuses=[make_status("etl_load")],
            label="before deploy",
        )
        d = snap.to_dict()
        assert "snapshot_id" in d
        assert "taken_at" in d
        assert "statuses" in d
        assert "label" in d

    def test_taken_at_is_iso_string(self):
        snap = Snapshot(snapshot_id="x", taken_at=_now(), statuses=[])
        d = snap.to_dict()
        datetime.fromisoformat(d["taken_at"])  # must not raise

    def test_statuses_serialised(self):
        snap = Snapshot(snapshot_id="x", taken_at=_now(), statuses=[make_status("job_a"), make_status("job_b")])
        d = snap.to_dict()
        assert len(d["statuses"]) == 2


class TestSnapshotFromDict:
    def test_roundtrip(self):
        original = Snapshot(
            snapshot_id="round-1",
            taken_at=_now(),
            statuses=[make_status("pipe_x")],
            label="test",
        )
        restored = Snapshot.from_dict(original.to_dict())
        assert restored.snapshot_id == original.snapshot_id
        assert restored.label == original.label
        assert len(restored.statuses) == 1
        assert restored.statuses[0].job_name == "pipe_x"


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "snaps.json"


@pytest.fixture
def store(store_path: Path) -> SnapshotStore:
    return SnapshotStore(store_path)


class TestSnapshotStore:
    def test_empty_store_returns_empty_list(self, store):
        assert store.list_snapshots() == []

    def test_save_and_list(self, store):
        store.save_snapshot([make_status("job_a")], label="v1")
        snaps = store.list_snapshots()
        assert len(snaps) == 1
        assert snaps[0].label == "v1"

    def test_get_snapshot_by_id(self, store):
        snap = store.save_snapshot([make_status("job_b")])
        fetched = store.get_snapshot(snap.snapshot_id)
        assert fetched is not None
        assert fetched.snapshot_id == snap.snapshot_id

    def test_get_nonexistent_returns_none(self, store):
        assert store.get_snapshot("does-not-exist") is None

    def test_delete_snapshot(self, store):
        snap = store.save_snapshot([make_status("job_c")])
        removed = store.delete_snapshot(snap.snapshot_id)
        assert removed is True
        assert store.get_snapshot(snap.snapshot_id) is None

    def test_delete_nonexistent_returns_false(self, store):
        assert store.delete_snapshot("ghost-id") is False

    def test_persists_across_instances(self, store_path):
        s1 = SnapshotStore(store_path)
        snap = s1.save_snapshot([make_status("job_d")])
        s2 = SnapshotStore(store_path)
        assert s2.get_snapshot(snap.snapshot_id) is not None
