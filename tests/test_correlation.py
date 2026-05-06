"""Tests for pipewatch.correlation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pipewatch.alert_rules import AlertEvent
from pipewatch.job_status import JobState
from pipewatch.correlation import CorrelationGroup, correlate_events


def _dt(offset_seconds: int = 0) -> datetime:
    base = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(seconds=offset_seconds)


def make_event(job: str, offset: int = 0) -> AlertEvent:
    return AlertEvent(
        job_name=job,
        rule_name="test_rule",
        state=JobState.FAILED,
        fired_at=_dt(offset),
    )


# ---------------------------------------------------------------------------
# CorrelationGroup
# ---------------------------------------------------------------------------

class TestCorrelationGroup:
    def test_is_cascade_single_job(self):
        grp = CorrelationGroup(
            anchor_job="job_a",
            events=[make_event("job_a"), make_event("job_a", 5)],
        )
        assert grp.is_cascade() is False

    def test_is_cascade_multiple_jobs(self):
        grp = CorrelationGroup(
            anchor_job="job_a",
            events=[make_event("job_a"), make_event("job_b", 5)],
        )
        assert grp.is_cascade() is True

    def test_to_dict_contains_required_keys(self):
        grp = CorrelationGroup(
            anchor_job="job_a",
            events=[make_event("job_a"), make_event("job_b", 10)],
        )
        d = grp.to_dict()
        for key in ("anchor_job", "job_count", "event_count", "is_cascade", "jobs", "window_seconds"):
            assert key in d

    def test_to_dict_job_count(self):
        grp = CorrelationGroup(
            anchor_job="job_a",
            events=[make_event("job_a"), make_event("job_a", 5), make_event("job_b", 10)],
        )
        assert grp.to_dict()["job_count"] == 2
        assert grp.to_dict()["event_count"] == 3


# ---------------------------------------------------------------------------
# correlate_events
# ---------------------------------------------------------------------------

class TestCorrelateEvents:
    def test_empty_returns_empty(self):
        assert correlate_events([]) == []

    def test_single_event_below_min_group_size(self):
        result = correlate_events([make_event("job_a")], min_group_size=2)
        assert result == []

    def test_two_close_events_form_group(self):
        events = [make_event("job_a", 0), make_event("job_b", 30)]
        groups = correlate_events(events, window_seconds=60)
        assert len(groups) == 1
        assert groups[0].is_cascade() is True

    def test_events_outside_window_split_into_separate_groups(self):
        events = [
            make_event("job_a", 0),
            make_event("job_b", 30),
            make_event("job_c", 200),
            make_event("job_d", 220),
        ]
        groups = correlate_events(events, window_seconds=60)
        assert len(groups) == 2

    def test_cascade_detected_across_jobs(self):
        events = [make_event(f"job_{i}", i * 10) for i in range(4)]
        groups = correlate_events(events, window_seconds=60)
        assert len(groups) == 1
        assert groups[0].is_cascade() is True

    def test_unsorted_events_are_sorted_internally(self):
        events = [make_event("job_b", 20), make_event("job_a", 0)]
        groups = correlate_events(events, window_seconds=60)
        assert len(groups) == 1
        assert groups[0].anchor_job == "job_a"

    def test_min_group_size_respected(self):
        events = [make_event("job_a", 0), make_event("job_b", 10), make_event("job_c", 20)]
        groups = correlate_events(events, window_seconds=60, min_group_size=3)
        assert len(groups) == 1
        groups2 = correlate_events(events[:2], window_seconds=60, min_group_size=3)
        assert len(groups2) == 0
