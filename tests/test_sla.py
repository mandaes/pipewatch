"""Tests for pipewatch.sla module."""
from datetime import datetime, timezone, timedelta
from typing import Optional

import pytest

from pipewatch.job_status import JobState, JobStatus
from pipewatch.sla import SLAPolicy, SLAViolation, check_sla, evaluate_slas


NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_status(
    job_name: str = "etl_load",
    state: JobState = JobState.SUCCESS,
    duration_seconds: Optional[float] = None,
    last_success: Optional[datetime] = None,
) -> JobStatus:
    return JobStatus(
        job_name=job_name,
        state=state,
        last_success=last_success,
        duration_seconds=duration_seconds,
    )


class TestSLAPolicyToDict:
    def test_contains_required_keys(self):
        policy = SLAPolicy(job_name="job_a", max_duration_seconds=300.0)
        d = policy.to_dict()
        assert d["job_name"] == "job_a"
        assert d["max_duration_seconds"] == 300.0
        assert "must_succeed_within_seconds" in d

    def test_none_values_serialised(self):
        policy = SLAPolicy(job_name="job_b")
        d = policy.to_dict()
        assert d["max_duration_seconds"] is None
        assert d["must_succeed_within_seconds"] is None


class TestSLAViolationToDict:
    def test_to_dict_contains_required_keys(self):
        v = SLAViolation(job_name="job_a", reason="too slow", checked_at=NOW)
        d = v.to_dict()
        assert d["job_name"] == "job_a"
        assert d["reason"] == "too slow"
        assert d["checked_at"] == NOW.isoformat()


class TestCheckSLA:
    def test_no_violation_when_duration_within_limit(self):
        policy = SLAPolicy(job_name="etl_load", max_duration_seconds=600.0)
        status = make_status(duration_seconds=300.0)
        assert check_sla(policy, status, now=NOW) is None

    def test_violation_when_duration_exceeds_limit(self):
        policy = SLAPolicy(job_name="etl_load", max_duration_seconds=100.0)
        status = make_status(duration_seconds=250.0)
        result = check_sla(policy, status, now=NOW)
        assert result is not None
        assert result.job_name == "etl_load"
        assert "250.0" in result.reason
        assert "100.0" in result.reason

    def test_no_violation_when_success_is_recent(self):
        policy = SLAPolicy(job_name="etl_load", must_succeed_within_seconds=3600.0)
        recent = NOW - timedelta(seconds=1800)
        status = make_status(last_success=recent)
        assert check_sla(policy, status, now=NOW) is None

    def test_violation_when_last_success_is_stale(self):
        policy = SLAPolicy(job_name="etl_load", must_succeed_within_seconds=3600.0)
        old = NOW - timedelta(seconds=7200)
        status = make_status(last_success=old)
        result = check_sla(policy, status, now=NOW)
        assert result is not None
        assert "7200" in result.reason

    def test_returns_none_for_wrong_job_name(self):
        policy = SLAPolicy(job_name="other_job", max_duration_seconds=10.0)
        status = make_status(job_name="etl_load", duration_seconds=999.0)
        assert check_sla(policy, status, now=NOW) is None

    def test_no_violation_when_duration_is_none(self):
        policy = SLAPolicy(job_name="etl_load", max_duration_seconds=10.0)
        status = make_status(duration_seconds=None)
        assert check_sla(policy, status, now=NOW) is None

    def test_violation_checked_at_uses_provided_now(self):
        policy = SLAPolicy(job_name="etl_load", max_duration_seconds=1.0)
        status = make_status(duration_seconds=999.0)
        result = check_sla(policy, status, now=NOW)
        assert result is not None
        assert result.checked_at == NOW


class TestEvaluateSLAs:
    def test_empty_policies_returns_empty(self):
        statuses = [make_status()]
        assert evaluate_slas([], statuses, now=NOW) == []

    def test_empty_statuses_returns_empty(self):
        policies = [SLAPolicy(job_name="etl_load", max_duration_seconds=10.0)]
        assert evaluate_slas(policies, [], now=NOW) == []

    def test_skips_policy_with_no_matching_status(self):
        policies = [SLAPolicy(job_name="missing_job", max_duration_seconds=1.0)]
        statuses = [make_status(job_name="other_job", duration_seconds=999.0)]
        assert evaluate_slas(policies, statuses, now=NOW) == []

    def test_returns_violations_for_multiple_jobs(self):
        policies = [
            SLAPolicy(job_name="job_a", max_duration_seconds=10.0),
            SLAPolicy(job_name="job_b", max_duration_seconds=10.0),
        ]
        statuses = [
            make_status(job_name="job_a", duration_seconds=50.0),
            make_status(job_name="job_b", duration_seconds=5.0),
        ]
        violations = evaluate_slas(policies, statuses, now=NOW)
        assert len(violations) == 1
        assert violations[0].job_name == "job_a"

    def test_returns_all_violations_when_multiple_breached(self):
        policies = [
            SLAPolicy(job_name="job_a", max_duration_seconds=1.0),
            SLAPolicy(job_name="job_b", max_duration_seconds=1.0),
        ]
        statuses = [
            make_status(job_name="job_a", duration_seconds=100.0),
            make_status(job_name="job_b", duration_seconds=200.0),
        ]
        violations = evaluate_slas(policies, statuses, now=NOW)
        assert len(violations) == 2
