"""Tests for pipewatch.cooldown."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from pipewatch.cooldown import CooldownPolicy, CooldownStore

_BASE = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def store_path(tmp_path):
    return str(tmp_path / "cooldown.json")


@pytest.fixture()
def store(store_path):
    return CooldownStore(path=store_path)


class TestCooldownPolicy:
    def test_defaults(self):
        p = CooldownPolicy()
        assert p.window_seconds == 300

    def test_to_dict(self):
        p = CooldownPolicy(window_seconds=60)
        assert p.to_dict() == {"window_seconds": 60}


class TestCooldownStore:
    def test_last_alerted_none_when_empty(self, store):
        assert store.last_alerted("etl_job", "failed") is None

    def test_record_and_retrieve(self, store):
        with patch("pipewatch.cooldown._utcnow", return_value=_BASE):
            store.record_alert("etl_job", "failed")
        ts = store.last_alerted("etl_job", "failed")
        assert ts == _BASE

    def test_persists_to_disk(self, store_path):
        s1 = CooldownStore(path=store_path)
        with patch("pipewatch.cooldown._utcnow", return_value=_BASE):
            s1.record_alert("job_a", "stale")
        s2 = CooldownStore(path=store_path)
        assert s2.last_alerted("job_a", "stale") == _BASE

    def test_is_cooling_down_true_within_window(self, store):
        policy = CooldownPolicy(window_seconds=300)
        with patch("pipewatch.cooldown._utcnow", return_value=_BASE):
            store.record_alert("job_a", "failed")
        later = _BASE + timedelta(seconds=100)
        with patch("pipewatch.cooldown._utcnow", return_value=later):
            assert store.is_cooling_down("job_a", "failed", policy) is True

    def test_is_cooling_down_false_after_window(self, store):
        policy = CooldownPolicy(window_seconds=300)
        with patch("pipewatch.cooldown._utcnow", return_value=_BASE):
            store.record_alert("job_a", "failed")
        later = _BASE + timedelta(seconds=400)
        with patch("pipewatch.cooldown._utcnow", return_value=later):
            assert store.is_cooling_down("job_a", "failed", policy) is False

    def test_is_cooling_down_false_when_no_entry(self, store):
        policy = CooldownPolicy(window_seconds=300)
        assert store.is_cooling_down("unknown", "failed", policy) is False

    def test_clear_removes_entry(self, store):
        with patch("pipewatch.cooldown._utcnow", return_value=_BASE):
            store.record_alert("job_x", "failed")
        store.clear("job_x", "failed")
        assert store.last_alerted("job_x", "failed") is None

    def test_clear_nonexistent_is_safe(self, store):
        store.clear("ghost_job", "stale")  # should not raise

    def test_keys_are_independent(self, store):
        policy = CooldownPolicy(window_seconds=300)
        with patch("pipewatch.cooldown._utcnow", return_value=_BASE):
            store.record_alert("job_a", "failed")
        later = _BASE + timedelta(seconds=10)
        with patch("pipewatch.cooldown._utcnow", return_value=later):
            assert store.is_cooling_down("job_a", "stale", policy) is False
            assert store.is_cooling_down("job_b", "failed", policy) is False
