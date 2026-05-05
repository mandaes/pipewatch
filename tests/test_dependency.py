"""Tests for pipewatch.dependency."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from pipewatch.job_status import JobState, JobStatus
from pipewatch.dependency import (
    BlockedJob,
    DependencyRule,
    find_blocked_jobs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_status(
    name: str,
    state: JobState = JobState.SUCCESS,
    last_success: Optional[datetime] = _NOW,
) -> JobStatus:
    return JobStatus(
        job_name=name,
        state=state,
        last_success=last_success,
        stale_after_minutes=60,
    )


# ---------------------------------------------------------------------------
# DependencyRule.to_dict
# ---------------------------------------------------------------------------


def test_to_dict_contains_job_and_requires():
    rule = DependencyRule(job="etl_load", requires=["etl_extract", "etl_transform"])
    d = rule.to_dict()
    assert d["job"] == "etl_load"
    assert d["requires"] == ["etl_extract", "etl_transform"]


# ---------------------------------------------------------------------------
# BlockedJob.to_dict
# ---------------------------------------------------------------------------


def test_blocked_job_to_dict():
    bj = BlockedJob(job="load", blocked_by="extract", upstream_state=JobState.FAILED)
    d = bj.to_dict()
    assert d["job"] == "load"
    assert d["blocked_by"] == "extract"
    assert d["upstream_state"] == "failed"


# ---------------------------------------------------------------------------
# find_blocked_jobs
# ---------------------------------------------------------------------------


class TestFindBlockedJobs:
    def test_no_rules_returns_empty(self):
        statuses = [make_status("job_a")]
        result = find_blocked_jobs([], statuses)
        assert result == []

    def test_healthy_upstream_not_blocked(self):
        rules = [DependencyRule(job="load", requires=["extract"])]
        statuses = [make_status("extract", JobState.SUCCESS), make_status("load")]
        result = find_blocked_jobs(rules, statuses)
        assert result == []

    def test_failed_upstream_blocks_downstream(self):
        rules = [DependencyRule(job="load", requires=["extract"])]
        statuses = [make_status("extract", JobState.FAILED), make_status("load")]
        result = find_blocked_jobs(rules, statuses)
        assert len(result) == 1
        assert result[0].job == "load"
        assert result[0].blocked_by == "extract"
        assert result[0].upstream_state == JobState.FAILED

    def test_stale_upstream_blocks_downstream(self):
        rules = [DependencyRule(job="load", requires=["extract"])]
        statuses = [make_status("extract", JobState.STALE), make_status("load")]
        result = find_blocked_jobs(rules, statuses)
        assert len(result) == 1
        assert result[0].upstream_state == JobState.STALE

    def test_unknown_upstream_treated_as_stale(self):
        rules = [DependencyRule(job="load", requires=["missing_job"])]
        statuses = [make_status("load")]
        result = find_blocked_jobs(rules, statuses)
        assert len(result) == 1
        assert result[0].blocked_by == "missing_job"
        assert result[0].upstream_state == JobState.STALE

    def test_multiple_requires_each_checked(self):
        rules = [DependencyRule(job="load", requires=["step_a", "step_b"])]
        statuses = [
            make_status("step_a", JobState.FAILED),
            make_status("step_b", JobState.SUCCESS),
            make_status("load"),
        ]
        result = find_blocked_jobs(rules, statuses)
        assert len(result) == 1
        assert result[0].blocked_by == "step_a"

    def test_custom_blocking_states(self):
        rules = [DependencyRule(job="load", requires=["extract"])]
        statuses = [make_status("extract", JobState.STALE), make_status("load")]
        # Only FAILED is blocking — STALE should not trigger
        result = find_blocked_jobs(rules, statuses, blocking_states=[JobState.FAILED])
        assert result == []

    def test_multiple_rules_independent(self):
        rules = [
            DependencyRule(job="report", requires=["load"]),
            DependencyRule(job="archive", requires=["report"]),
        ]
        statuses = [
            make_status("load", JobState.FAILED),
            make_status("report", JobState.SUCCESS),
            make_status("archive"),
        ]
        result = find_blocked_jobs(rules, statuses)
        assert len(result) == 1
        assert result[0].job == "report"
        assert result[0].blocked_by == "load"
