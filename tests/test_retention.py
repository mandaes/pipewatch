"""Tests for pipewatch.retention."""

from __future__ import annotations

import datetime
from typing import List

import pytest

from pipewatch.history import HistoryEntry
from pipewatch.job_status import JobState
from pipewatch.retention import RetentionPolicy, prune_entries, prune_store

NOW = datetime.datetime(2024, 6, 1, 12, 0, 0)


def make_entry(job: str, days_ago: float, state: JobState = JobState.SUCCESS) -> HistoryEntry:
    checked_at = NOW - datetime.timedelta(days=days_ago)
    return HistoryEntry(
        job_name=job,
        state=state,
        checked_at=checked_at,
        last_success=checked_at if state == JobState.SUCCESS else None,
    )


class TestRetentionPolicyToDict:
    def test_both_none(self):
        p = RetentionPolicy()
        d = p.to_dict()
        assert d["max_age_days"] is None
        assert d["max_entries"] is None

    def test_values_preserved(self):
        p = RetentionPolicy(max_age_days=30, max_entries=100)
        d = p.to_dict()
        assert d["max_age_days"] == 30
        assert d["max_entries"] == 100


class TestPruneEntries:
    def test_empty_list_returns_empty(self):
        policy = RetentionPolicy(max_age_days=7)
        assert prune_entries([], policy, now=NOW) == []

    def test_max_age_removes_old_entries(self):
        entries = [make_entry("job", days_ago=d) for d in [1, 5, 10, 20]]
        policy = RetentionPolicy(max_age_days=7)
        result = prune_entries(entries, policy, now=NOW)
        assert len(result) == 2  # 1-day and 5-day entries survive

    def test_max_age_keeps_boundary_entry(self):
        entries = [make_entry("job", days_ago=7)]
        policy = RetentionPolicy(max_age_days=7)
        result = prune_entries(entries, policy, now=NOW)
        assert len(result) == 1

    def test_max_entries_keeps_most_recent(self):
        entries = [make_entry("job", days_ago=d) for d in [1, 3, 5, 8, 12]]
        policy = RetentionPolicy(max_entries=3)
        result = prune_entries(entries, policy, now=NOW)
        assert len(result) == 3
        ages = [(NOW - e.checked_at).days for e in result]
        assert max(ages) <= 5  # the three newest

    def test_combined_policy(self):
        entries = [make_entry("job", days_ago=d) for d in [1, 2, 3, 15]]
        policy = RetentionPolicy(max_age_days=10, max_entries=2)
        result = prune_entries(entries, policy, now=NOW)
        assert len(result) == 2

    def test_no_policy_keeps_all(self):
        entries = [make_entry("job", days_ago=d) for d in range(50)]
        policy = RetentionPolicy()
        result = prune_entries(entries, policy, now=NOW)
        assert len(result) == 50


class TestPruneStore:
    def test_applies_to_all_jobs(self):
        store = {
            "alpha": [make_entry("alpha", d) for d in [1, 20]],
            "beta": [make_entry("beta", d) for d in [2, 25]],
        }
        policy = RetentionPolicy(max_age_days=10)
        result = prune_store(store, policy, now=NOW)
        assert len(result["alpha"]) == 1
        assert len(result["beta"]) == 1

    def test_does_not_mutate_input(self):
        store = {"job": [make_entry("job", 1), make_entry("job", 30)]}
        original_len = len(store["job"])
        policy = RetentionPolicy(max_age_days=10)
        prune_store(store, policy, now=NOW)
        assert len(store["job"]) == original_len

    def test_empty_store_returns_empty(self):
        result = prune_store({}, RetentionPolicy(max_age_days=7), now=NOW)
        assert result == {}
