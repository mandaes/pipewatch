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
    def test_report_contains_expected_keys(self):
        entries = [
            make_entry("job_a", JobState.SUCCESS),
            make_entry("job_a", JobState.FAILED),
        ]
        report = job_report("job_a", entries)
        assert "job_id" in report
        assert "total_checks" in report
        assert "failure_rate" in report
        assert "last_state" in report
        assert "state_summary" in report

    def test_report_job_id_matches(self):
        entries = [make_entry("my_job", JobState.SUCCESS)]
        report = job_report("my_job", entries)
        assert report["job_id"] == "my_job"

    def test_report_total_checks(self):
        entries = [
            make_entry("job_a", JobState.SUCCESS),
            make_entry("job_a", JobState.SUCCESS),
            make_entry("job_a", JobState.FAILED),
        ]
        report = job_report("job_a", entries)
        assert report["total_checks"] == 3

    def test_report_failure_rate_value(self):
        entries = [
            make_entry("job_a", JobState.SUCCESS),
            make_entry("job_a", JobState.FAILED),
        ]
        report = job_report("job_a", entries)
        assert report["failure_rate"] == pytest.approx(0.5)

    def test_empty_entries_report(self):
        report = job_report("empty_job", [])
        assert report["total_checks"] == 0
        assert report["failure_rate"] == 0.0
        assert report["last_state"] is None


class TestAllJobsReport:
    def test_empty_history_returns_empty_list(self):
        result = all_jobs_report({})
        assert result == []

    def test_single_job_report(self):
        history = {
            "job_a": [make_entry("job_a", JobState.SUCCESS)]
        }
        result = all_jobs_report(history)
        assert len(result) == 1
        assert result[0]["job_id"] == "job_a"

    def test_multiple_jobs_report(self):
        history = {
            "job_a": [make_entry("job_a", JobState.SUCCESS)],
            "job_b": [make_entry("job_b", JobState.FAILED)],
            "job_c": [make_entry("job_c", JobState.STALE)],
        }
        result = all_jobs_report(history)
        assert len(result) == 3
        job_ids = {r["job_id"] for r in result}
        assert job_ids == {"job_a", "job_b", "job_c"}
