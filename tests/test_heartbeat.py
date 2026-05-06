"""Tests for pipewatch.heartbeat."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from pipewatch.heartbeat import HeartbeatRecord, HeartbeatStore


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_record(
    job_name: str = "etl_job",
    last_seen: datetime | None = None,
    expected_interval_seconds: int = 300,
) -> HeartbeatRecord:
    return HeartbeatRecord(
        job_name=job_name,
        last_seen=last_seen or _now(),
        expected_interval_seconds=expected_interval_seconds,
    )


# ---------------------------------------------------------------------------
# HeartbeatRecord
# ---------------------------------------------------------------------------

class TestHeartbeatRecordIsMissing:
    def test_fresh_record_is_not_missing(self):
        r = make_record(last_seen=_now())
        assert r.is_missing() is False

    def test_overdue_record_is_missing(self):
        old = _now() - timedelta(seconds=600)
        r = make_record(last_seen=old, expected_interval_seconds=300)
        assert r.is_missing() is True

    def test_exactly_on_boundary_is_not_missing(self):
        now = _now()
        last = now - timedelta(seconds=300)
        r = make_record(last_seen=last, expected_interval_seconds=300)
        # elapsed == interval → not yet overdue
        assert r.is_missing(now=now) is False

    def test_one_second_over_is_missing(self):
        now = _now()
        last = now - timedelta(seconds=301)
        r = make_record(last_seen=last, expected_interval_seconds=300)
        assert r.is_missing(now=now) is True


class TestHeartbeatRecordSecondsOverdue:
    def test_negative_when_on_time(self):
        now = _now()
        r = make_record(last_seen=now, expected_interval_seconds=300)
        assert r.seconds_overdue(now=now) < 0

    def test_positive_when_overdue(self):
        now = _now()
        last = now - timedelta(seconds=400)
        r = make_record(last_seen=last, expected_interval_seconds=300)
        assert r.seconds_overdue(now=now) == pytest.approx(100, abs=1)


class TestHeartbeatRecordSerialization:
    def test_to_dict_contains_required_keys(self):
        r = make_record()
        d = r.to_dict()
        assert set(d.keys()) == {"job_name", "last_seen", "expected_interval_seconds"}

    def test_from_dict_roundtrip(self):
        r = make_record(job_name="loader", expected_interval_seconds=120)
        r2 = HeartbeatRecord.from_dict(r.to_dict())
        assert r2.job_name == r.job_name
        assert r2.expected_interval_seconds == r.expected_interval_seconds
        assert r2.last_seen == r.last_seen


# ---------------------------------------------------------------------------
# HeartbeatStore
# ---------------------------------------------------------------------------

@pytest.fixture()
def store_path(tmp_path):
    return str(tmp_path / "heartbeats.json")


@pytest.fixture()
def store(store_path):
    return HeartbeatStore(path=store_path)


class TestHeartbeatStore:
    def test_touch_creates_record(self, store):
        r = store.touch("job_a", 300)
        assert r.job_name == "job_a"

    def test_touch_persists_to_disk(self, store, store_path):
        store.touch("job_b", 60)
        with open(store_path) as fh:
            data = json.load(fh)
        assert "job_b" in data

    def test_get_returns_none_for_unknown_job(self, store):
        assert store.get("nonexistent") is None

    def test_get_returns_record_after_touch(self, store):
        store.touch("job_c", 600)
        assert store.get("job_c") is not None

    def test_missing_jobs_empty_when_all_fresh(self, store):
        store.touch("job_d", 300)
        assert store.missing_jobs() == []

    def test_missing_jobs_detects_overdue(self, store_path):
        # Manually write a stale record
        stale_time = (_now() - timedelta(seconds=999)).isoformat()
        with open(store_path, "w") as fh:
            json.dump(
                {"stale": {"job_name": "stale", "last_seen": stale_time, "expected_interval_seconds": 60}},
                fh,
            )
        s = HeartbeatStore(path=store_path)
        missing = s.missing_jobs()
        assert len(missing) == 1
        assert missing[0].job_name == "stale"

    def test_all_records_returns_all(self, store):
        store.touch("j1", 100)
        store.touch("j2", 200)
        assert len(store.all_records()) == 2

    def test_store_loads_existing_file(self, store_path):
        s1 = HeartbeatStore(path=store_path)
        s1.touch("persistent_job", 500)
        s2 = HeartbeatStore(path=store_path)
        assert s2.get("persistent_job") is not None
