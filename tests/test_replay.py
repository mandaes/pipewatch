"""Tests for pipewatch.replay."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pipewatch.alert_rules import AlertRule
from pipewatch.history import HistoryEntry
from pipewatch.job_status import JobState
from pipewatch.replay import ReplayResult, replay, _entry_to_status


def _now() -> datetime:
    return datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_entry(
    job_name: str = "etl_load",
    state: JobState = JobState.SUCCESS,
    tags: list | None = None,
) -> HistoryEntry:
    return HistoryEntry(
        job_name=job_name,
        state=state,
        started_at=_now(),
        finished_at=_now(),
        tags=tags or [],
    )


# ---------------------------------------------------------------------------
# _entry_to_status
# ---------------------------------------------------------------------------

class TestEntryToStatus:
    def test_job_name_preserved(self):
        entry = make_entry(job_name="my_job")
        status = _entry_to_status(entry)
        assert status.job_name == "my_job"

    def test_success_sets_last_success(self):
        entry = make_entry(state=JobState.SUCCESS)
        status = _entry_to_status(entry)
        assert status.last_success == entry.finished_at

    def test_failed_last_success_is_none(self):
        entry = make_entry(state=JobState.FAILED)
        status = _entry_to_status(entry)
        assert status.last_success is None

    def test_tags_preserved(self):
        entry = make_entry(tags=["env:prod", "team:data"])
        status = _entry_to_status(entry)
        assert status.tags == ["env:prod", "team:data"]


# ---------------------------------------------------------------------------
# replay
# ---------------------------------------------------------------------------

class TestReplay:
    def _failed_rule(self, job: str = "etl_load") -> AlertRule:
        return AlertRule(job_name=job, match_states=[JobState.FAILED], severity="critical")

    def test_empty_entries_returns_zero_matched(self):
        result = replay([], rules=[self._failed_rule()])
        assert result.total_entries == 0
        assert result.matched_events == []

    def test_matching_entry_produces_event(self):
        entries = [make_entry(state=JobState.FAILED)]
        result = replay(entries, rules=[self._failed_rule()])
        assert len(result.matched_events) == 1
        assert result.matched_events[0].job_name == "etl_load"

    def test_success_entry_does_not_match_failed_rule(self):
        entries = [make_entry(state=JobState.SUCCESS)]
        result = replay(entries, rules=[self._failed_rule()])
        assert result.matched_events == []

    def test_job_filter_skips_other_jobs(self):
        entries = [
            make_entry(job_name="etl_load", state=JobState.FAILED),
            make_entry(job_name="etl_transform", state=JobState.FAILED),
        ]
        rules = [
            self._failed_rule("etl_load"),
            self._failed_rule("etl_transform"),
        ]
        result = replay(entries, rules=rules, job_filter=["etl_load"])
        assert len(result.matched_events) == 1
        assert "etl_transform" in result.skipped_jobs

    def test_to_dict_contains_required_keys(self):
        result = ReplayResult(total_entries=3)
        d = result.to_dict()
        assert "total_entries" in d
        assert "matched_count" in d
        assert "skipped_jobs" in d
        assert "events" in d

    def test_total_entries_reflects_input_length(self):
        entries = [make_entry() for _ in range(5)]
        result = replay(entries, rules=[])
        assert result.total_entries == 5
