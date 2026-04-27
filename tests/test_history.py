"""Tests for pipewatch.history module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from pipewatch.history import HistoryEntry, HistoryStore


def make_entry(job_name: str = "etl_job", state: str = "success", last_success: str = "2024-01-01T00:00:00+00:00") -> HistoryEntry:
    return HistoryEntry(job_name=job_name, state=state, last_success=last_success)


@pytest.fixture
def tmp_store(tmp_path: Path) -> HistoryStore:
    return HistoryStore(path=tmp_path / "history.jsonl")


class TestHistoryEntry:
    def test_to_dict_contains_required_keys(self):
        entry = make_entry()
        d = entry.to_dict()
        assert "job_name" in d
        assert "state" in d
        assert "last_success" in d
        assert "recorded_at" in d

    def test_from_dict_roundtrip(self):
        entry = make_entry(job_name="pipeline_a", state="failed")
        restored = HistoryEntry.from_dict(entry.to_dict())
        assert restored.job_name == entry.job_name
        assert restored.state == entry.state
        assert restored.last_success == entry.last_success
        assert restored.recorded_at == entry.recorded_at

    def test_recorded_at_is_set_automatically(self):
        entry = make_entry()
        assert entry.recorded_at is not None
        assert "T" in entry.recorded_at

    def test_explicit_recorded_at_preserved(self):
        ts = "2024-06-15T12:00:00+00:00"
        entry = HistoryEntry(job_name="j", state="success", last_success=None, recorded_at=ts)
        assert entry.recorded_at == ts


class TestHistoryStore:
    def test_append_and_read_all(self, tmp_store: HistoryStore):
        entry = make_entry()
        tmp_store.append(entry)
        results = tmp_store.read_all()
        assert len(results) == 1
        assert results[0].job_name == entry.job_name

    def test_read_all_empty_when_no_file(self, tmp_store: HistoryStore):
        assert tmp_store.read_all() == []

    def test_multiple_entries_preserved_in_order(self, tmp_store: HistoryStore):
        for state in ["success", "failed", "stale"]:
            tmp_store.append(make_entry(state=state))
        results = tmp_store.read_all()
        assert [r.state for r in results] == ["success", "failed", "stale"]

    def test_recent_for_job_filters_by_name(self, tmp_store: HistoryStore):
        tmp_store.append(make_entry(job_name="job_a", state="success"))
        tmp_store.append(make_entry(job_name="job_b", state="failed"))
        tmp_store.append(make_entry(job_name="job_a", state="stale"))
        results = tmp_store.recent_for_job("job_a")
        assert len(results) == 2
        assert all(r.job_name == "job_a" for r in results)

    def test_recent_for_job_respects_limit(self, tmp_store: HistoryStore):
        for i in range(10):
            tmp_store.append(make_entry(job_name="job_x", state="success"))
        results = tmp_store.recent_for_job("job_x", limit=3)
        assert len(results) == 3

    def test_clear_removes_file(self, tmp_store: HistoryStore):
        tmp_store.append(make_entry())
        assert tmp_store.path.exists()
        tmp_store.clear()
        assert not tmp_store.path.exists()

    def test_skips_malformed_lines(self, tmp_store: HistoryStore):
        with tmp_store.path.open("w") as fh:
            fh.write("not json\n")
            fh.write(json.dumps(make_entry().to_dict()) + "\n")
        results = tmp_store.read_all()
        assert len(results) == 1
