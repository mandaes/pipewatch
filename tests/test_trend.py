"""Tests for pipewatch.trend — trend direction analysis."""

from datetime import datetime, timezone
from typing import List

import pytest

from pipewatch.history import HistoryEntry
from pipewatch.job_status import JobState
from pipewatch.trend import (
    TrendDirection,
    TrendResult,
    analyze_trend,
    _failure_rate,
)


def make_entry(state: JobState, ts: str = "2024-01-01T00:00:00+00:00") -> HistoryEntry:
    return HistoryEntry(
        job_name="test_job",
        state=state,
        polled_at=datetime.fromisoformat(ts),
    )


def entries(pattern: List[JobState]) -> List[HistoryEntry]:
    """Build a list of HistoryEntry from a list of states."""
    return [make_entry(s) for s in pattern]


# ---------------------------------------------------------------------------
# _failure_rate
# ---------------------------------------------------------------------------

class TestFailureRate:
    def test_empty_returns_zero(self):
        assert _failure_rate([]) == 0.0

    def test_all_success(self):
        assert _failure_rate(entries([JobState.SUCCESS] * 4)) == 0.0

    def test_all_failed(self):
        assert _failure_rate(entries([JobState.FAILED] * 4)) == 1.0

    def test_stale_counts_as_failure(self):
        rate = _failure_rate(entries([JobState.STALE, JobState.SUCCESS]))
        assert rate == 0.5

    def test_mixed(self):
        pattern = [JobState.FAILED, JobState.SUCCESS, JobState.SUCCESS, JobState.FAILED]
        assert _failure_rate(entries(pattern)) == 0.5


# ---------------------------------------------------------------------------
# analyze_trend
# ---------------------------------------------------------------------------

class TestAnalyzeTrend:
    def test_insufficient_data_below_min_samples(self):
        result = analyze_trend("job", entries([JobState.FAILED] * 4), min_samples=6)
        assert result.direction == TrendDirection.INSUFFICIENT_DATA
        assert result.sample_size == 4

    def test_stable_all_success(self):
        pattern = [JobState.SUCCESS] * 10
        result = analyze_trend("job", entries(pattern))
        assert result.direction == TrendDirection.STABLE
        assert result.failure_rate_recent == 0.0
        assert result.failure_rate_older == 0.0

    def test_degrading_when_recent_failures_spike(self):
        # older half: all success; recent half: all failed
        pattern = [JobState.SUCCESS] * 6 + [JobState.FAILED] * 6
        result = analyze_trend("job", entries(pattern), threshold=0.15)
        assert result.direction == TrendDirection.DEGRADING
        assert result.failure_rate_recent == 1.0
        assert result.failure_rate_older == 0.0

    def test_improving_when_recent_failures_drop(self):
        # older half: all failed; recent half: all success
        pattern = [JobState.FAILED] * 6 + [JobState.SUCCESS] * 6
        result = analyze_trend("job", entries(pattern), threshold=0.15)
        assert result.direction == TrendDirection.IMPROVING

    def test_stable_within_threshold(self):
        # 1 failure in each half of 6 → rates equal
        half = [JobState.FAILED] + [JobState.SUCCESS] * 5
        result = analyze_trend("job", entries(half + half), threshold=0.15)
        assert result.direction == TrendDirection.STABLE

    def test_to_dict_keys(self):
        pattern = [JobState.SUCCESS] * 8
        result = analyze_trend("myjob", entries(pattern))
        d = result.to_dict()
        assert set(d.keys()) == {
            "job_name", "direction", "failure_rate_recent",
            "failure_rate_older", "sample_size",
        }
        assert d["job_name"] == "myjob"
        assert d["sample_size"] == 8

    def test_job_name_propagated(self):
        result = analyze_trend("etl_load", entries([JobState.SUCCESS] * 6))
        assert result.job_name == "etl_load"
