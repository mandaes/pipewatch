"""Tests for pipewatch.circuit_breaker."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from pipewatch.circuit_breaker import (
    BreakerRecord,
    BreakerState,
    CircuitBreakerPolicy,
    CircuitBreakerStore,
)


_EPOCH = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _now() -> datetime:
    return _EPOCH


@pytest.fixture
def store_path(tmp_path):
    return str(tmp_path / "breakers.json")


@pytest.fixture
def store(store_path):
    return CircuitBreakerStore(store_path)


@pytest.fixture
def policy():
    return CircuitBreakerPolicy(failure_threshold=3, recovery_window_seconds=300, success_threshold=1)


# ---------------------------------------------------------------------------
# CircuitBreakerPolicy
# ---------------------------------------------------------------------------

class TestCircuitBreakerPolicy:
    def test_defaults(self):
        p = CircuitBreakerPolicy()
        assert p.failure_threshold == 3
        assert p.recovery_window_seconds == 300
        assert p.success_threshold == 1

    def test_to_dict_contains_required_keys(self):
        d = CircuitBreakerPolicy().to_dict()
        assert "failure_threshold" in d
        assert "recovery_window_seconds" in d
        assert "success_threshold" in d


# ---------------------------------------------------------------------------
# BreakerRecord
# ---------------------------------------------------------------------------

class TestBreakerRecord:
    def test_to_dict_roundtrip(self):
        rec = BreakerRecord(
            job="etl_load",
            state=BreakerState.OPEN,
            consecutive_failures=5,
            consecutive_successes=0,
            tripped_at=_EPOCH,
        )
        d = rec.to_dict()
        restored = BreakerRecord.from_dict(d)
        assert restored.job == rec.job
        assert restored.state == rec.state
        assert restored.consecutive_failures == rec.consecutive_failures
        assert restored.tripped_at == rec.tripped_at

    def test_from_dict_no_tripped_at(self):
        rec = BreakerRecord.from_dict({"job": "x"})
        assert rec.tripped_at is None
        assert rec.state == BreakerState.CLOSED


# ---------------------------------------------------------------------------
# CircuitBreakerStore — failure recording
# ---------------------------------------------------------------------------

class TestRecordFailure:
    def test_single_failure_stays_closed(self, store, policy):
        with patch("pipewatch.circuit_breaker._utcnow", _now):
            rec = store.record_failure("job_a", policy)
        assert rec.state == BreakerState.CLOSED
        assert rec.consecutive_failures == 1

    def test_threshold_trips_breaker(self, store, policy):
        with patch("pipewatch.circuit_breaker._utcnow", _now):
            for _ in range(3):
                rec = store.record_failure("job_a", policy)
        assert rec.state == BreakerState.OPEN
        assert rec.tripped_at == _EPOCH

    def test_failure_persisted_to_disk(self, store, store_path, policy):
        with patch("pipewatch.circuit_breaker._utcnow", _now):
            store.record_failure("job_b", policy)
        assert os.path.exists(store_path)
        with open(store_path) as fh:
            data = json.load(fh)
        assert "job_b" in data


# ---------------------------------------------------------------------------
# CircuitBreakerStore — success recording
# ---------------------------------------------------------------------------

class TestRecordSuccess:
    def test_success_resets_failure_count(self, store, policy):
        with patch("pipewatch.circuit_breaker._utcnow", _now):
            store.record_failure("job_a", policy)
            store.record_failure("job_a", policy)
            rec = store.record_success("job_a", policy)
        assert rec.consecutive_failures == 0
        assert rec.state == BreakerState.CLOSED

    def test_success_in_half_open_closes_breaker(self, store, policy):
        # Trip the breaker first
        with patch("pipewatch.circuit_breaker._utcnow", _now):
            for _ in range(3):
                store.record_failure("job_a", policy)

        # Advance time past recovery window
        future = _EPOCH + timedelta(seconds=400)
        with patch("pipewatch.circuit_breaker._utcnow", lambda: future):
            rec = store.record_success("job_a", policy)

        assert rec.state == BreakerState.CLOSED


# ---------------------------------------------------------------------------
# CircuitBreakerStore — is_open
# ---------------------------------------------------------------------------

class TestIsOpen:
    def test_closed_breaker_not_open(self, store, policy):
        with patch("pipewatch.circuit_breaker._utcnow", _now):
            assert not store.is_open("job_a", policy)

    def test_open_breaker_within_window_is_open(self, store, policy):
        with patch("pipewatch.circuit_breaker._utcnow", _now):
            for _ in range(3):
                store.record_failure("job_a", policy)
            assert store.is_open("job_a", policy)

    def test_open_breaker_past_window_not_open(self, store, policy):
        with patch("pipewatch.circuit_breaker._utcnow", _now):
            for _ in range(3):
                store.record_failure("job_a", policy)

        future = _EPOCH + timedelta(seconds=400)
        with patch("pipewatch.circuit_breaker._utcnow", lambda: future):
            assert not store.is_open("job_a", policy)

    def test_unknown_job_not_open(self, store, policy):
        assert not store.is_open("nonexistent", policy)

    def test_all_records_returns_list(self, store, policy):
        with patch("pipewatch.circuit_breaker._utcnow", _now):
            store.record_failure("job_x", policy)
            store.record_failure("job_y", policy)
        records = store.all_records()
        jobs = {r.job for r in records}
        assert "job_x" in jobs
        assert "job_y" in jobs
