"""Tests for pipewatch.budget."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from pipewatch.budget import BudgetPolicy, BudgetStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def store_path(tmp_path):
    return str(tmp_path / "budget.json")


@pytest.fixture
def store(store_path):
    return BudgetStore(path=store_path)


_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _dt(offset_seconds: int = 0) -> datetime:
    return _NOW + timedelta(seconds=offset_seconds)


# ---------------------------------------------------------------------------
# BudgetPolicy
# ---------------------------------------------------------------------------

class TestBudgetPolicy:
    def test_defaults(self):
        p = BudgetPolicy()
        assert p.max_alerts == 10
        assert p.window_seconds == 3600

    def test_to_dict_contains_required_keys(self):
        p = BudgetPolicy(max_alerts=5, window_seconds=600)
        d = p.to_dict()
        assert d["max_alerts"] == 5
        assert d["window_seconds"] == 600


# ---------------------------------------------------------------------------
# BudgetStore
# ---------------------------------------------------------------------------

class TestBudgetStoreAlertCount:
    def test_zero_when_no_alerts(self, store):
        p = BudgetPolicy()
        assert store.alert_count("job_a", p.window_seconds) == 0

    def test_increments_after_record(self, store):
        with patch("pipewatch.budget._utcnow", return_value=_NOW):
            store.record_alert("job_a")
            store.record_alert("job_a")
        assert store.alert_count("job_a", 3600) == 2

    def test_old_alerts_pruned(self, store):
        old = _dt(-7200)  # 2 hours ago
        with patch("pipewatch.budget._utcnow", return_value=old):
            store.record_alert("job_a")
        with patch("pipewatch.budget._utcnow", return_value=_NOW):
            count = store.alert_count("job_a", 3600)
        assert count == 0


class TestBudgetStoreIsExhausted:
    def test_not_exhausted_when_under_limit(self, store):
        p = BudgetPolicy(max_alerts=3, window_seconds=3600)
        with patch("pipewatch.budget._utcnow", return_value=_NOW):
            store.record_alert("job_b")
            store.record_alert("job_b")
        assert not store.is_exhausted("job_b", p)

    def test_exhausted_at_limit(self, store):
        p = BudgetPolicy(max_alerts=2, window_seconds=3600)
        with patch("pipewatch.budget._utcnow", return_value=_NOW):
            store.record_alert("job_b")
            store.record_alert("job_b")
        assert store.is_exhausted("job_b", p)

    def test_remaining_decrements(self, store):
        p = BudgetPolicy(max_alerts=5, window_seconds=3600)
        with patch("pipewatch.budget._utcnow", return_value=_NOW):
            store.record_alert("job_c")
            store.record_alert("job_c")
        assert store.remaining("job_c", p) == 3

    def test_remaining_never_negative(self, store):
        p = BudgetPolicy(max_alerts=1, window_seconds=3600)
        with patch("pipewatch.budget._utcnow", return_value=_NOW):
            store.record_alert("job_c")
            store.record_alert("job_c")
        assert store.remaining("job_c", p) == 0


class TestBudgetStoreReset:
    def test_reset_clears_history(self, store):
        with patch("pipewatch.budget._utcnow", return_value=_NOW):
            store.record_alert("job_d")
        store.reset("job_d")
        assert store.alert_count("job_d", 3600) == 0

    def test_reset_unknown_job_is_noop(self, store):
        store.reset("nonexistent")  # should not raise

    def test_persisted_to_disk(self, store, store_path):
        with patch("pipewatch.budget._utcnow", return_value=_NOW):
            store.record_alert("job_e")
        assert os.path.exists(store_path)
        with open(store_path) as fh:
            data = json.load(fh)
        assert "job_e" in data
