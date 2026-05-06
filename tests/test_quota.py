"""Tests for pipewatch.quota."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from pipewatch.quota import QuotaPolicy, QuotaStore

_BASE = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _now():
    return _BASE


@pytest.fixture
def store_path(tmp_path):
    return str(tmp_path / "quota.json")


@pytest.fixture
def store(store_path):
    return QuotaStore(path=store_path)


class TestQuotaPolicy:
    def test_defaults(self):
        p = QuotaPolicy()
        assert p.max_alerts == 10
        assert p.window_seconds == 3600

    def test_to_dict_contains_required_keys(self):
        p = QuotaPolicy(max_alerts=5, window_seconds=600)
        d = p.to_dict()
        assert d["max_alerts"] == 5
        assert d["window_seconds"] == 600


class TestQuotaStore:
    def test_new_event_is_not_exceeded(self, store):
        policy = QuotaPolicy(max_alerts=3)
        assert not store.is_exceeded("job_a", policy)

    def test_record_returns_true_when_under_quota(self, store):
        policy = QuotaPolicy(max_alerts=3)
        with patch("pipewatch.quota._utcnow", _now):
            assert store.record("job_a", policy) is True

    def test_record_returns_false_when_quota_exceeded(self, store):
        policy = QuotaPolicy(max_alerts=2)
        with patch("pipewatch.quota._utcnow", _now):
            store.record("job_a", policy)
            store.record("job_a", policy)
            result = store.record("job_a", policy)
        assert result is False

    def test_alert_count_tracks_records(self, store):
        policy = QuotaPolicy(max_alerts=10)
        with patch("pipewatch.quota._utcnow", _now):
            store.record("job_b", policy)
            store.record("job_b", policy)
        assert store.alert_count("job_b", policy) == 2

    def test_old_alerts_pruned_outside_window(self, store):
        policy = QuotaPolicy(max_alerts=2, window_seconds=60)
        old_ts = (_BASE - timedelta(seconds=120)).isoformat()
        store._data["job_c"] = [old_ts, old_ts]
        assert store.alert_count("job_c", policy) == 0
        assert not store.is_exceeded("job_c", policy)

    def test_reset_single_job(self, store):
        policy = QuotaPolicy(max_alerts=10)
        with patch("pipewatch.quota._utcnow", _now):
            store.record("job_d", policy)
        store.reset("job_d")
        assert store.alert_count("job_d", policy) == 0

    def test_reset_all_jobs(self, store):
        policy = QuotaPolicy(max_alerts=10)
        with patch("pipewatch.quota._utcnow", _now):
            store.record("job_e", policy)
            store.record("job_f", policy)
        store.reset()
        assert store.alert_count("job_e", policy) == 0
        assert store.alert_count("job_f", policy) == 0

    def test_persists_to_disk(self, store_path):
        policy = QuotaPolicy(max_alerts=10)
        s1 = QuotaStore(path=store_path)
        with patch("pipewatch.quota._utcnow", _now):
            s1.record("job_g", policy)
        s2 = QuotaStore(path=store_path)
        assert s2.alert_count("job_g", policy) == 1
