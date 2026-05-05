"""Tests for pipewatch.checkpoint and pipewatch.cli_checkpoint."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from pipewatch.checkpoint import Checkpoint, CheckpointStore, is_regressed
from pipewatch.cli_checkpoint import main, parse_args


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_checkpoint(job="etl_daily", marker="2024-01-10T00:00:00+00:00") -> Checkpoint:
    return Checkpoint(job_name=job, marker=marker, recorded_at=_now())


@pytest.fixture
def store_path(tmp_path):
    return str(tmp_path / "checkpoints.json")


# ---------------------------------------------------------------------------
# Checkpoint dataclass
# ---------------------------------------------------------------------------

class TestCheckpoint:
    def test_to_dict_contains_required_keys(self):
        cp = make_checkpoint()
        d = cp.to_dict()
        assert "job_name" in d
        assert "marker" in d
        assert "recorded_at" in d

    def test_from_dict_roundtrip(self):
        cp = make_checkpoint()
        restored = Checkpoint.from_dict(cp.to_dict())
        assert restored.job_name == cp.job_name
        assert restored.marker == cp.marker

    def test_recorded_at_is_iso_string_in_dict(self):
        cp = make_checkpoint()
        d = cp.to_dict()
        # Should not raise
        datetime.fromisoformat(d["recorded_at"])


# ---------------------------------------------------------------------------
# CheckpointStore
# ---------------------------------------------------------------------------

class TestCheckpointStore:
    def test_get_returns_none_for_unknown_job(self, store_path):
        s = CheckpointStore(store_path)
        assert s.get("missing") is None

    def test_save_and_get_roundtrip(self, store_path):
        s = CheckpointStore(store_path)
        cp = make_checkpoint()
        s.save(cp)
        result = s.get(cp.job_name)
        assert result is not None
        assert result.marker == cp.marker

    def test_save_overwrites_previous(self, store_path):
        s = CheckpointStore(store_path)
        s.save(make_checkpoint(marker="2024-01-01T00:00:00+00:00"))
        s.save(make_checkpoint(marker="2024-02-01T00:00:00+00:00"))
        assert s.get("etl_daily").marker == "2024-02-01T00:00:00+00:00"

    def test_all_returns_all_jobs(self, store_path):
        s = CheckpointStore(store_path)
        s.save(make_checkpoint(job="job_a"))
        s.save(make_checkpoint(job="job_b"))
        assert len(s.all()) == 2

    def test_delete_removes_entry(self, store_path):
        s = CheckpointStore(store_path)
        s.save(make_checkpoint())
        removed = s.delete("etl_daily")
        assert removed is True
        assert s.get("etl_daily") is None

    def test_delete_returns_false_for_missing(self, store_path):
        s = CheckpointStore(store_path)
        assert s.delete("ghost") is False

    def test_persists_to_disk(self, store_path):
        s = CheckpointStore(store_path)
        s.save(make_checkpoint())
        s2 = CheckpointStore(store_path)
        assert s2.get("etl_daily") is not None


# ---------------------------------------------------------------------------
# is_regressed
# ---------------------------------------------------------------------------

def test_is_regressed_detects_older_marker():
    prev = make_checkpoint(marker="2024-03-01T00:00:00+00:00")
    cur = make_checkpoint(marker="2024-01-01T00:00:00+00:00")
    assert is_regressed(prev, cur) is True


def test_is_not_regressed_for_newer_marker():
    prev = make_checkpoint(marker="2024-01-01T00:00:00+00:00")
    cur = make_checkpoint(marker="2024-03-01T00:00:00+00:00")
    assert is_regressed(prev, cur) is False


def test_equal_markers_not_regressed():
    cp = make_checkpoint(marker="2024-01-01T00:00:00+00:00")
    assert is_regressed(cp, cp) is False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCLI:
    def test_record_and_list(self, store_path, capsys):
        main(["--store", store_path, "record", "job_x", "2024-05-01T00:00:00+00:00"])
        main(["--store", store_path, "list"])
        out = capsys.readouterr().out
        assert "job_x" in out

    def test_show_missing_returns_nonzero(self, store_path):
        rc = main(["--store", store_path, "show", "no_such_job"])
        assert rc == 1

    def test_delete_existing(self, store_path):
        main(["--store", store_path, "record", "job_y", "marker1"])
        rc = main(["--store", store_path, "delete", "job_y"])
        assert rc == 0

    def test_check_regression_detected(self, store_path):
        main(["--store", store_path, "record", "job_z", "2024-06-01"])
        rc = main(["--store", store_path, "check-regression", "job_z", "2024-01-01"])
        assert rc == 2

    def test_check_regression_ok(self, store_path):
        main(["--store", store_path, "record", "job_z", "2024-01-01"])
        rc = main(["--store", store_path, "check-regression", "job_z", "2024-06-01"])
        assert rc == 0

    def test_check_regression_no_previous(self, store_path, capsys):
        rc = main(["--store", store_path, "check-regression", "new_job", "2024-06-01"])
        assert rc == 0
