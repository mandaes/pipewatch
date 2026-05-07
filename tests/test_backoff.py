"""Tests for pipewatch.backoff."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pipewatch.backoff import BackoffPolicy, BackoffState, BackoffStore


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# BackoffPolicy
# ---------------------------------------------------------------------------

class TestBackoffPolicy:
    def test_defaults(self):
        p = BackoffPolicy()
        assert p.base_seconds == 60.0
        assert p.multiplier == 2.0
        assert p.max_seconds == 3600.0
        assert p.max_attempts is None

    def test_to_dict_contains_required_keys(self):
        p = BackoffPolicy()
        d = p.to_dict()
        for key in ("base_seconds", "multiplier", "max_seconds", "max_attempts"):
            assert key in d

    def test_delay_attempt_1_equals_base(self):
        p = BackoffPolicy(base_seconds=30.0, multiplier=2.0)
        assert p.delay_for_attempt(1) == 30.0

    def test_delay_doubles_each_attempt(self):
        p = BackoffPolicy(base_seconds=10.0, multiplier=2.0, max_seconds=9999)
        assert p.delay_for_attempt(2) == pytest.approx(20.0)
        assert p.delay_for_attempt(3) == pytest.approx(40.0)

    def test_delay_capped_at_max(self):
        p = BackoffPolicy(base_seconds=100.0, multiplier=10.0, max_seconds=500.0)
        assert p.delay_for_attempt(5) == 500.0

    def test_delay_attempt_zero_returns_zero(self):
        p = BackoffPolicy()
        assert p.delay_for_attempt(0) == 0.0


# ---------------------------------------------------------------------------
# BackoffState
# ---------------------------------------------------------------------------

class TestBackoffState:
    def test_should_notify_when_never_notified(self):
        state = BackoffState(job_name="etl_load")
        policy = BackoffPolicy()
        assert state.should_notify(policy) is True

    def test_should_not_notify_before_delay_elapsed(self):
        now = _now()
        state = BackoffState(job_name="etl_load", attempt=1, last_notified_at=now)
        policy = BackoffPolicy(base_seconds=300.0)
        # Only 1 second later — well within the 300 s window
        assert state.should_notify(policy, now=now + timedelta(seconds=1)) is False

    def test_should_notify_after_delay_elapsed(self):
        past = _now() - timedelta(seconds=400)
        state = BackoffState(job_name="etl_load", attempt=1, last_notified_at=past)
        policy = BackoffPolicy(base_seconds=300.0)
        assert state.should_notify(policy) is True

    def test_record_notification_increments_attempt(self):
        state = BackoffState(job_name="etl_load")
        state.record_notification()
        assert state.attempt == 1
        assert state.last_notified_at is not None

    def test_reset_clears_state(self):
        state = BackoffState(job_name="etl_load", attempt=5, last_notified_at=_now())
        state.reset()
        assert state.attempt == 0
        assert state.last_notified_at is None

    def test_max_attempts_blocks_notification(self):
        state = BackoffState(job_name="etl_load", attempt=3)
        policy = BackoffPolicy(max_attempts=3)
        assert state.should_notify(policy) is False


# ---------------------------------------------------------------------------
# BackoffStore
# ---------------------------------------------------------------------------

@pytest.fixture()
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "backoff.json"


@pytest.fixture()
def store(store_path: Path) -> BackoffStore:
    return BackoffStore(store_path)


class TestBackoffStore:
    def test_get_returns_fresh_state_for_unknown_job(self, store: BackoffStore):
        s = store.get("new_job")
        assert s.attempt == 0
        assert s.last_notified_at is None

    def test_save_and_reload(self, store_path: Path):
        s1 = BackoffStore(store_path)
        state = s1.get("job_a")
        state.record_notification()
        s1.save_state(state)

        s2 = BackoffStore(store_path)
        loaded = s2.get("job_a")
        assert loaded.attempt == 1
        assert loaded.last_notified_at is not None

    def test_remove_deletes_entry(self, store: BackoffStore, store_path: Path):
        state = store.get("job_b")
        state.record_notification()
        store.save_state(state)
        store.remove("job_b")
        assert store.get("job_b").attempt == 0

    def test_persisted_file_is_valid_json(self, store: BackoffStore, store_path: Path):
        state = store.get("job_c")
        state.record_notification()
        store.save_state(state)
        data = json.loads(store_path.read_text())
        assert "job_c" in data
