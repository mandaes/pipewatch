"""Tests for pipewatch.dedup."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from pipewatch.alert_rules import AlertEvent
from pipewatch.dedup import DedupStore


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_event(rule: str = "stale_check", job: str = "etl_main") -> AlertEvent:
    return AlertEvent(rule_name=rule, job_name=job, state="stale", message="stale job")


@pytest.fixture()
def store(tmp_path: Path) -> DedupStore:
    return DedupStore(str(tmp_path / "dedup.json"), cooldown_minutes=60)


class TestIsDuplicate:
    def test_new_event_is_not_duplicate(self, store: DedupStore) -> None:
        assert store.is_duplicate(make_event()) is False

    def test_recorded_event_is_duplicate(self, store: DedupStore) -> None:
        event = make_event()
        store.record(event)
        assert store.is_duplicate(event) is True

    def test_expired_event_is_not_duplicate(self, store: DedupStore) -> None:
        event = make_event()
        past = _now() - timedelta(minutes=120)
        with patch("pipewatch.dedup._utcnow", return_value=past):
            store.record(event)
        assert store.is_duplicate(event) is False

    def test_different_jobs_are_independent(self, store: DedupStore) -> None:
        e1 = make_event(job="job_a")
        e2 = make_event(job="job_b")
        store.record(e1)
        assert store.is_duplicate(e2) is False

    def test_different_rules_are_independent(self, store: DedupStore) -> None:
        e1 = make_event(rule="rule_a")
        e2 = make_event(rule="rule_b")
        store.record(e1)
        assert store.is_duplicate(e2) is False


class TestFilterNew:
    def test_all_new_events_pass_through(self, store: DedupStore) -> None:
        events = [make_event(job="a"), make_event(job="b")]
        result = store.filter_new(events)
        assert len(result) == 2

    def test_duplicate_event_suppressed(self, store: DedupStore) -> None:
        event = make_event()
        store.filter_new([event])
        result = store.filter_new([event])
        assert result == []

    def test_mixed_events_only_new_returned(self, store: DedupStore) -> None:
        old_event = make_event(job="old")
        new_event = make_event(job="new")
        store.record(old_event)
        result = store.filter_new([old_event, new_event])
        assert len(result) == 1
        assert result[0].job_name == "new"


class TestPersistence:
    def test_records_saved_to_disk(self, tmp_path: Path) -> None:
        store = DedupStore(str(tmp_path / "dedup.json"))
        store.record(make_event())
        assert (tmp_path / "dedup.json").exists()

    def test_records_reloaded_on_init(self, tmp_path: Path) -> None:
        path = str(tmp_path / "dedup.json")
        s1 = DedupStore(path)
        s1.record(make_event())
        s2 = DedupStore(path)
        assert s2.is_duplicate(make_event()) is True

    def test_corrupt_file_yields_empty_store(self, tmp_path: Path) -> None:
        p = tmp_path / "dedup.json"
        p.write_text("not valid json")
        store = DedupStore(str(p))
        assert store.is_duplicate(make_event()) is False


class TestPurgeExpired:
    def test_purge_removes_old_entries(self, tmp_path: Path) -> None:
        store = DedupStore(str(tmp_path / "dedup.json"), cooldown_minutes=60)
        past = _now() - timedelta(minutes=120)
        with patch("pipewatch.dedup._utcnow", return_value=past):
            store.record(make_event(job="old"))
        store.record(make_event(job="fresh"))
        removed = store.purge_expired()
        assert removed == 1
        assert store.is_duplicate(make_event(job="fresh")) is True
        assert store.is_duplicate(make_event(job="old")) is False

    def test_purge_returns_zero_when_nothing_expired(self, store: DedupStore) -> None:
        store.record(make_event())
        assert store.purge_expired() == 0
