"""Tests for pipewatch.anomaly."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from pipewatch.anomaly import (
    AnomalyKind,
    analyze_anomalies,
    detect_duration_spike,
    detect_failure_spike,
)
from pipewatch.history import HistoryEntry
from pipewatch.job_status import JobState


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def make_entry(
    state: JobState = JobState.SUCCESS,
    duration_seconds: float = 60.0,
    offset_minutes: int = 0,
) -> HistoryEntry:
    finished = _now() - timedelta(minutes=offset_minutes)
    started = finished - timedelta(seconds=duration_seconds)
    return HistoryEntry(
        job_name="test_job",
        state=state,
        polled_at=finished,
        started_at=started,
        finished_at=finished,
    )


# ---------------------------------------------------------------------------
# detect_duration_spike
# ---------------------------------------------------------------------------

class TestDetectDurationSpike:
    def test_returns_none_when_too_few_entries(self):
        entries = [make_entry(duration_seconds=300)] * 2
        assert detect_duration_spike("job", entries) is None

    def test_no_spike_for_uniform_durations(self):
        entries = [make_entry(duration_seconds=60)] * 10
        assert detect_duration_spike("job", entries) is None

    def test_detects_spike_on_outlier(self):
        normal = [make_entry(duration_seconds=60)] * 9
        outlier = make_entry(duration_seconds=600)
        result = detect_duration_spike("job", normal + [outlier])
        assert result is not None
        assert result.kind == AnomalyKind.DURATION_SPIKE
        assert result.score > 0
        assert "std-devs" in result.detail

    def test_score_capped_at_one(self):
        normal = [make_entry(duration_seconds=10)] * 9
        outlier = make_entry(duration_seconds=10_000)
        result = detect_duration_spike("job", normal + [outlier], z_threshold=2.5)
        assert result is not None
        assert result.score <= 1.0


# ---------------------------------------------------------------------------
# detect_failure_spike
# ---------------------------------------------------------------------------

class TestDetectFailureSpike:
    def test_returns_none_for_empty(self):
        assert detect_failure_spike("job", []) is None

    def test_no_spike_all_success(self):
        entries = [make_entry(state=JobState.SUCCESS)] * 5
        assert detect_failure_spike("job", entries) is None

    def test_detects_spike_majority_failures(self):
        entries = [make_entry(state=JobState.FAILED)] * 4 + [make_entry(state=JobState.SUCCESS)]
        result = detect_failure_spike("job", entries, window=5, threshold=0.6)
        assert result is not None
        assert result.kind == AnomalyKind.FAILURE_SPIKE
        assert "4/5" in result.detail

    def test_window_limits_lookback(self):
        old_failures = [make_entry(state=JobState.FAILED)] * 10
        recent_success = [make_entry(state=JobState.SUCCESS)] * 5
        result = detect_failure_spike("job", old_failures + recent_success, window=5)
        assert result is None


# ---------------------------------------------------------------------------
# analyze_anomalies
# ---------------------------------------------------------------------------

class TestAnalyzeAnomalies:
    def test_empty_entries_returns_no_runs(self):
        results = analyze_anomalies("job", [])
        assert len(results) == 1
        assert results[0].kind == AnomalyKind.NO_RUNS
        assert results[0].score == 1.0

    def test_healthy_job_returns_empty(self):
        entries = [make_entry(state=JobState.SUCCESS, duration_seconds=60)] * 10
        assert analyze_anomalies("job", entries) == []

    def test_to_dict_has_required_keys(self):
        entries = [make_entry(state=JobState.FAILED)] * 5
        results = analyze_anomalies("job", entries)
        assert results
        d = results[0].to_dict()
        for key in ("job_name", "kind", "detail", "score"):
            assert key in d

    def test_multiple_anomalies_can_be_returned(self):
        normal = [make_entry(state=JobState.FAILED, duration_seconds=60)] * 4
        outlier = make_entry(state=JobState.FAILED, duration_seconds=6000)
        results = analyze_anomalies("job", normal + [outlier])
        kinds = {r.kind for r in results}
        assert AnomalyKind.FAILURE_SPIKE in kinds
