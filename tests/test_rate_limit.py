"""Tests for pipewatch.rate_limit."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta

import pytest

from pipewatch.rate_limit import RateLimitPolicy, RateLimitStore


def _dt(offset_seconds: float = 0.0) -> datetime:
    return datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc) + timedelta(
        seconds=offset_seconds
    )


@pytest.fixture
def store(tmp_path):
    return RateLimitStore(path=str(tmp_path / "rate_limit.json"))


class TestRateLimitPolicy:
    def test_defaults(self):
        p = RateLimitPolicy()
        assert p.max_alerts == 3
        assert p.window_seconds == 3600

    def test_to_dict(self):
        p = RateLimitPolicy(max_alerts=5, window_seconds=600)
        d = p.to_dict()
        assert d["max_alerts"] == 5
        assert d["window_seconds"] == 600


class TestRateLimitStore:
    def test_new_event_is_allowed(self, store):
        policy = RateLimitPolicy(max_alerts=3, window_seconds=3600)
        assert store.is_allowed("job_a", "rule_x", policy, now=_dt()) is True

    def test_allowed_until_limit_reached(self, store):
        policy = RateLimitPolicy(max_alerts=2, window_seconds=3600)
        now = _dt()
        store.record("job_a", "rule_x", now=now)
        assert store.is_allowed("job_a", "rule_x", policy, now=_dt(10)) is True
        store.record("job_a", "rule_x", now=_dt(10))
        assert store.is_allowed("job_a", "rule_x", policy, now=_dt(20)) is False

    def test_blocked_after_max_alerts(self, store):
        policy = RateLimitPolicy(max_alerts=1, window_seconds=3600)
        store.record("job_b", "rule_y", now=_dt())
        assert store.is_allowed("job_b", "rule_y", policy, now=_dt(1)) is False

    def test_window_expiry_re_allows(self, store):
        policy = RateLimitPolicy(max_alerts=1, window_seconds=60)
        store.record("job_c", "rule_z", now=_dt())
        # Still blocked within window
        assert store.is_allowed("job_c", "rule_z", policy, now=_dt(30)) is False
        # Allowed after window expires
        assert store.is_allowed("job_c", "rule_z", policy, now=_dt(61)) is True

    def test_count_returns_correct_number(self, store):
        policy = RateLimitPolicy(max_alerts=5, window_seconds=3600)
        for i in range(3):
            store.record("job_d", "rule_w", now=_dt(i))
        assert store.count("job_d", "rule_w", policy, now=_dt(10)) == 3

    def test_count_excludes_expired(self, store):
        policy = RateLimitPolicy(max_alerts=5, window_seconds=100)
        store.record("job_e", "rule_v", now=_dt(0))
        store.record("job_e", "rule_v", now=_dt(50))
        # First entry expired, second still valid
        assert store.count("job_e", "rule_v", policy, now=_dt(110)) == 1

    def test_different_jobs_independent(self, store):
        policy = RateLimitPolicy(max_alerts=1, window_seconds=3600)
        store.record("job_a", "rule_x", now=_dt())
        # job_b should be unaffected
        assert store.is_allowed("job_b", "rule_x", policy, now=_dt(1)) is True

    def test_persists_across_instances(self, tmp_path):
        path = str(tmp_path / "rl.json")
        policy = RateLimitPolicy(max_alerts=2, window_seconds=3600)
        s1 = RateLimitStore(path=path)
        s1.record("job_f", "rule_u", now=_dt())
        s2 = RateLimitStore(path=path)
        assert s2.count("job_f", "rule_u", policy, now=_dt(10)) == 1

    def test_empty_store_count_is_zero(self, store):
        policy = RateLimitPolicy()
        assert store.count("nonexistent", "rule", policy, now=_dt()) == 0
