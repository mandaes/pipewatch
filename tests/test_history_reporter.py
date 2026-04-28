"""Tests for pipewatch.history_reporter module."""

import pytest
from datetime import datetime, timezone
from pipewatch.history import HistoryEntry
from pipewatch.job_status import JobState
from pipewatch.history_reporter import (
    state_summary,
    failure_rate,
    last_state,
    job_report,
    all_jobs_report,
)


def make_entry(job_id: str, state: JobState, minutes_ago: int = 0) -> HistoryEntry:
    """Create a HistoryEntry for testing."""
    ts = datetime.now(timezone.utc).replace(microsecond=0)
    entry = HistoryEntry(
        job_id=job_id,
        state=state,
        checked_at=ts,
        last_success=None,
    )
    return entry


class TestStateSummary:
    def test_empty_entries_returns_zero_counts(self):
        result = state_summary([])
        assert result == {}

    def test_single_success(self):
        entries = [make_entry("job_a", JobState.SUCCESS)]
        result = state_summary(entries)
        assert result.get(JobState.SUCCESS, 0) == 1

    def test_mixed_states(self):
        entries = [
            make_entry("job_a", JobState.SUCCESS),
            make_entry("job_a", JobState.FAILED),
            make_entry("job_a", JobState.SUCCESS),
            make_entry("job_a", JobState.STALE),
        ]
        result = state_summary(entries)
        assert result[JobState.SUCCESS] == 2
        assert result[JobState.FAILED] == 1
        assert result[JobState.STALE] == 1


class TestFailureRate:
    def test_no_entries_returns_zero(self):
        assert failure_rate([]) == 0.0

    def test_all_success_returns_zero(self):
        entries = [
            make_entry("job_a", JobState.SUCCESS),
            make_entry("job_a", JobState.SUCCESS),
        ]
        assert failure_rate(entries) == 0.0

    def test_all_failed_returns_one(self):
        entries = [
            make_entry("job_a", JobState.FAILED),
            make_entry("job_a", JobState.FAILED),
        ]
        assert failure_rate(entries) == 1.0

    def test_half_failed(self):
        entries = [
            make_entry("job_a", JobState.SUCCESS),
            make_entry("job_a", JobState.FAILED),
        ]
        assert failure_rate(entries) == pytest.approx(0.5)

    def test_stale_not_counted_as_failure(self):
        entries = [
            make_entry("job_a", JobState.SUCCESS),
            make_entry("job_a", JobState.STALE),
        ]
        assert failure_rate(entries) == 0.0


class TestLastState:
    def test_empty_returns_none(self):
        assert last_state([]) is None

    def test_returns_state_of_last_entry(self):
        entries = [
            make_entry("job_a", JobState.SUCCESS),
            make_entry("job_a", JobState.FAILED),
        ]
        # last_state should return the state of the most recently appended entry
        assert last_state(entries) == JobState.FAILED

    def test_single_entry(self):
        entries = [make_entry("job_a", JobState.STALE)]
        assert last_state(entries) == JobState.STALE


class TestJobReport:
    def test_returns_dict_with_expected_keys(self):
        entries = [
            make_entry("job_a", JobState.SUCCESS),
            make_entry("job_a", JobState.FAILED),
        ]
        report = job_report("job_a", entries)
        assert "job_id" in report
        assert "last_state" in report
        assert "failure_rate" in report
        assert "state_summary" in report

    def test_job_id_matches(self):
        entries = [make_entry("job_a", JobState.SUCCESS)]
        report = job_report("job_a", entries)
        assert report["job_id"] == "job_a"

    def test_empty_entries(self):
        report = job_report("job_a", [])
        assert report["last_state"] is None
        assert report["failure_rate"] == 0.0
        assert report["state_summary"] == {}
