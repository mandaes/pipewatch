"""Tests for pipewatch.alert_rules."""

import pytest
from datetime import datetime, timezone, timedelta
from pipewatch.job_status import JobStatus, JobState
from pipewatch.alert_rules import AlertRule, AlertEvent, evaluate_rules


def make_status(
    job_name: str = "etl_job",
    state: JobState = JobState.SUCCESS,
    last_success: datetime = None,
    consecutive_failures: int = 0,
    stale_threshold_minutes: int = 60,
) -> JobStatus:
    if last_success is None:
        last_success = datetime.now(timezone.utc) - timedelta(minutes=5)
    return JobStatus(
        job_name=job_name,
        state=state,
        last_success=last_success,
        consecutive_failures=consecutive_failures,
        stale_threshold_minutes=stale_threshold_minutes,
    )


class TestAlertRuleMatches:
    def test_matches_failed_state(self):
        rule = AlertRule(name="r1", job_name="etl_job")
        status = make_status(state=JobState.FAILED, consecutive_failures=1)
        assert rule.matches(status)

    def test_no_match_on_success(self):
        rule = AlertRule(name="r1", job_name="etl_job")
        status = make_status(state=JobState.SUCCESS)
        assert not rule.matches(status)

    def test_no_match_wrong_job(self):
        rule = AlertRule(name="r1", job_name="other_job")
        status = make_status(state=JobState.FAILED, consecutive_failures=1)
        assert not rule.matches(status)

    def test_disabled_rule_never_matches(self):
        rule = AlertRule(name="r1", job_name="etl_job", enabled=False)
        status = make_status(state=JobState.FAILED, consecutive_failures=5)
        assert not rule.matches(status)

    def test_min_consecutive_failures_threshold(self):
        rule = AlertRule(name="r1", job_name="etl_job", min_consecutive_failures=3)
        status_low = make_status(state=JobState.FAILED, consecutive_failures=2)
        status_high = make_status(state=JobState.FAILED, consecutive_failures=3)
        assert not rule.matches(status_low)
        assert rule.matches(status_high)

    def test_matches_stale_state(self):
        rule = AlertRule(name="r1", job_name="etl_job")
        old_time = datetime.now(timezone.utc) - timedelta(hours=3)
        status = make_status(state=JobState.SUCCESS, last_success=old_time, stale_threshold_minutes=60)
        assert rule.matches(status)


class TestEvaluateRules:
    def test_returns_events_for_matching_rules(self):
        rule = AlertRule(name="r1", job_name="etl_job")
        status = make_status(state=JobState.FAILED, consecutive_failures=1)
        events = evaluate_rules([rule], [status])
        assert len(events) == 1
        assert events[0].rule_name == "r1"
        assert events[0].job_name == "etl_job"

    def test_no_events_when_no_match(self):
        rule = AlertRule(name="r1", job_name="etl_job")
        status = make_status(state=JobState.SUCCESS)
        events = evaluate_rules([rule], [status])
        assert events == []

    def test_missing_job_skipped(self):
        rule = AlertRule(name="r1", job_name="missing_job")
        status = make_status(job_name="etl_job", state=JobState.FAILED, consecutive_failures=1)
        events = evaluate_rules([rule], [status])
        assert events == []

    def test_event_to_dict(self):
        event = AlertEvent(
            rule_name="r1", job_name="etl_job",
            state=JobState.FAILED, message="Job failed", consecutive_failures=2
        )
        d = event.to_dict()
        assert d["state"] == "failed"
        assert d["consecutive_failures"] == 2
