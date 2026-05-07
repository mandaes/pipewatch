"""Tests for pipewatch.jitter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from pipewatch.history import HistoryEntry
from pipewatch.job_status import JobState
from pipewatch.jitter import JitterResult, detect_jitter

_BASE = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_entry(duration_seconds: float, offset_hours: int = 0) -> HistoryEntry:
    started = _BASE + timedelta(hours=offset_hours)
    finished = started + timedelta(seconds=duration_seconds)
    return HistoryEntry(
        job_name="etl_load",
        state=JobState.SUCCESS,
        recorded_at=finished,
        started_at=started,
        finished_at=finished,
    )


def uniform_entries(duration: float, count: int) -> List[HistoryEntry]:
    return [make_entry(duration, i) for i in range(count)]


def varied_entries(durations: List[float]) -> List[HistoryEntry]:
    return [make_entry(d, i) for i, d in enumerate(durations)]


# ---------------------------------------------------------------------------
# detect_jitter – insufficient samples
# ---------------------------------------------------------------------------

class TestDetectJitterTooFewSamples:
    def test_returns_none_when_empty(self):
        assert detect_jitter("etl_load", []) is None

    def test_returns_none_below_min_samples(self):
        entries = uniform_entries(60.0, 4)
        assert detect_jitter("etl_load", entries) is None

    def test_returns_result_at_exact_min_samples(self):
        entries = uniform_entries(60.0, 5)
        result = detect_jitter("etl_load", entries)
        assert result is not None


# ---------------------------------------------------------------------------
# detect_jitter – stable durations (no jitter)
# ---------------------------------------------------------------------------

class TestDetectJitterStable:
    def test_uniform_durations_not_jittery(self):
        entries = uniform_entries(120.0, 10)
        result = detect_jitter("etl_load", entries)
        assert result is not None
        assert result.is_jittery is False

    def test_cv_near_zero_for_uniform(self):
        entries = uniform_entries(100.0, 8)
        result = detect_jitter("etl_load", entries)
        assert result.cv < 0.01

    def test_zero_mean_not_jittery(self):
        # entries with zero duration (started == finished)
        entries = uniform_entries(0.0, 6)
        result = detect_jitter("etl_load", entries)
        assert result is not None
        assert result.is_jittery is False
        assert result.cv == 0.0


# ---------------------------------------------------------------------------
# detect_jitter – high variance (jitter detected)
# ---------------------------------------------------------------------------

class TestDetectJitterHigh:
    def test_high_variance_is_jittery(self):
        # durations ranging from 10 s to 1000 s → very high CV
        entries = varied_entries([10, 50, 500, 1000, 20, 800])
        result = detect_jitter("etl_load", entries)
        assert result is not None
        assert result.is_jittery is True

    def test_custom_threshold_respected(self):
        entries = varied_entries([100, 110, 90, 105, 95, 115])
        # CV will be small; with a very low threshold it should trigger
        result = detect_jitter("etl_load", entries, cv_threshold=0.01)
        assert result is not None
        assert result.is_jittery is True


# ---------------------------------------------------------------------------
# JitterResult.to_dict
# ---------------------------------------------------------------------------

class TestJitterResultToDict:
    def test_contains_required_keys(self):
        entries = uniform_entries(60.0, 5)
        result = detect_jitter("etl_load", entries)
        d = result.to_dict()
        for key in ("job_name", "mean_seconds", "stddev_seconds", "cv", "is_jittery", "sample_count"):
            assert key in d

    def test_sample_count_matches(self):
        entries = uniform_entries(60.0, 7)
        result = detect_jitter("etl_load", entries)
        assert result.to_dict()["sample_count"] == 7

    def test_job_name_preserved(self):
        entries = uniform_entries(30.0, 5)
        result = detect_jitter("my_job", entries)
        assert result.to_dict()["job_name"] == "my_job"
